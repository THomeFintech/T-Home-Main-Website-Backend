"""add user_documents table

Revision ID: add_user_documents
Revises: <your_previous_revision>
Create Date: 2024-01-01 00:00:00.000000

Changes from original:
- Removed file_data (LargeBinary) — files are stored in Cloudinary, not the DB
- Added file_url (String) — Cloudinary secure HTTPS URL
- Added public_id (String) — Cloudinary public_id used for deletion/replace
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision      = 'add_user_documents'
down_revision = None   # ← replace with your latest revision id
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # Create the enum type first (checkfirst=True is safe to re-run)
    documentstatus = postgresql.ENUM(
        'Verified', 'Pending Review', 'Action Required',
        name='documentstatus',
        create_type=True,
    )
    documentstatus.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'user_documents',

        sa.Column('id',             sa.Integer(),    nullable=False),
        sa.Column('application_id', sa.Integer(),    nullable=False),

        # Document metadata
        sa.Column('document_name',  sa.String(255),  nullable=False),
        sa.Column('category',       sa.String(100),  nullable=False, server_default='Other'),
        sa.Column(
            'status',
            sa.Enum('Verified', 'Pending Review', 'Action Required', name='documentstatus'),
            nullable=False,
            server_default='Pending Review',
        ),

        # Cloudinary storage — NO LargeBinary / file_data
        sa.Column('file_url',  sa.String(), nullable=True),   # Cloudinary secure URL
        sa.Column('public_id', sa.String(), nullable=True),   # Cloudinary public_id

        # File metadata
        sa.Column('filename',    sa.String(255), nullable=True),
        sa.Column('mimetype',    sa.String(100), nullable=True),
        sa.Column('file_size',   sa.Integer(),   nullable=True),

        # Reviewer note
        sa.Column('notes',       sa.Text(),      nullable=True),

        # Timestamps
        sa.Column('uploaded_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at',  sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['application_id'], ['loan_records.id'],
            ondelete='CASCADE',
        ),
    )

    op.create_index('ix_user_documents_id',             'user_documents', ['id'])
    op.create_index('ix_user_documents_application_id', 'user_documents', ['application_id'])


def downgrade() -> None:
    op.drop_index('ix_user_documents_application_id', table_name='user_documents')
    op.drop_index('ix_user_documents_id',             table_name='user_documents')
    op.drop_table('user_documents')
    sa.Enum(name='documentstatus').drop(op.get_bind(), checkfirst=True)