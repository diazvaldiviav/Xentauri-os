"""create oauth_credentials table

Revision ID: c3a5b8f2d9e1
Revises: b29e6844a7d1
Create Date: 2025-12-04 14:00:00.000000

Sprint 3.5: Google OAuth + Calendar Integration

This migration adds the oauth_credentials table for storing OAuth tokens
from external providers (Google, Microsoft, Apple, etc.).

The table is designed to:
1. Support multiple OAuth providers per user
2. Store access tokens, refresh tokens, and metadata
3. Track token expiration for automatic refresh
4. Store granted scopes for permission verification
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision: str = 'c3a5b8f2d9e1'
down_revision: Union[str, None] = 'b29e6844a7d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the oauth_credentials table."""
    op.create_table(
        'oauth_credentials',
        # Primary key
        sa.Column('id', UUID(), nullable=False),
        
        # Foreign key to users table
        sa.Column('user_id', UUID(), nullable=False),
        
        # Provider identification
        sa.Column('provider', sa.String(length=50), nullable=False),
        
        # Token data
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_type', sa.String(length=50), nullable=True),
        
        # Token metadata
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scopes', JSON(), nullable=True),
        
        # Provider-specific data
        sa.Column('extra_data', JSON(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    
    # Index on user_id for fast lookups
    op.create_index(
        op.f('ix_oauth_credentials_user_id'),
        'oauth_credentials',
        ['user_id'],
        unique=False
    )
    
    # Index on provider for filtering by provider
    op.create_index(
        op.f('ix_oauth_credentials_provider'),
        'oauth_credentials',
        ['provider'],
        unique=False
    )
    
    # Unique constraint: one provider per user
    # A user can only have one set of credentials per provider
    op.create_unique_constraint(
        'uq_oauth_credentials_user_provider',
        'oauth_credentials',
        ['user_id', 'provider']
    )


def downgrade() -> None:
    """Drop the oauth_credentials table."""
    op.drop_constraint('uq_oauth_credentials_user_provider', 'oauth_credentials', type_='unique')
    op.drop_index(op.f('ix_oauth_credentials_provider'), table_name='oauth_credentials')
    op.drop_index(op.f('ix_oauth_credentials_user_id'), table_name='oauth_credentials')
    op.drop_table('oauth_credentials')
