"""update_user_roles_with_rbac

Revision ID: 9b8c74d3e5a1
Revises: 8140d4aff684
Create Date: 2026-05-26 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import select, func
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = '9b8c74d3e5a1'
down_revision = '8140d4aff684'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Update user roles to match RBAC system:
    - First user created in each agency becomes 'admin'
    - All other users become 'recruiter'
    """
    conn = op.get_bind()
    session = Session(bind=conn)

    # Get all users ordered by creation date within each agency
    result = conn.execute(
        sa.text("""
            WITH ranked_users AS (
                SELECT 
                    id,
                    agency_id,
                    role,
                    ROW_NUMBER() OVER (PARTITION BY agency_id ORDER BY created_at ASC) as rn
                FROM users
            )
            SELECT id, agency_id, role, rn
            FROM ranked_users
        """)
    )

    updates_admin = []
    updates_recruiter = []

    for row in result:
        user_id, agency_id, current_role, row_num = row
        
        if row_num == 1:
            # First user in agency should be admin
            if current_role != 'admin':
                updates_admin.append(str(user_id))
        else:
            # Other users should be recruiter
            if current_role != 'recruiter':
                updates_recruiter.append(str(user_id))

    # Apply updates
    if updates_admin:
        conn.execute(
            sa.text(f"""
                UPDATE users 
                SET role = 'admin' 
                WHERE id::text IN ({','.join(f"'{uid}'" for uid in updates_admin)})
            """)
        )
        print(f"✓ Updated {len(updates_admin)} user(s) to 'admin' role")

    if updates_recruiter:
        conn.execute(
            sa.text(f"""
                UPDATE users 
                SET role = 'recruiter' 
                WHERE id::text IN ({','.join(f"'{uid}'" for uid in updates_recruiter)})
            """)
        )
        print(f"✓ Updated {len(updates_recruiter)} user(s) to 'recruiter' role")

    # Add check constraint to ensure only valid roles
    op.create_check_constraint(
        'users_role_check',
        'users',
        "role IN ('admin', 'recruiter')"
    )


def downgrade() -> None:
    """
    Revert role updates (all back to 'admin' for safety).
    """
    op.drop_constraint('users_role_check', 'users', type_='check')
    
    # For safety, set all users back to admin on downgrade
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE users SET role = 'admin'")
    )
