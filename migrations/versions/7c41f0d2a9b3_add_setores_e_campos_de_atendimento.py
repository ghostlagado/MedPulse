"""Adiciona setores, priorização e campos de integração em atendimentos

Revision ID: 7c41f0d2a9b3
Revises: b9e5006050e8
Create Date: 2026-10-17 14:05:12.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c41f0d2a9b3'
down_revision = 'b9e5006050e8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('hospitais', sa.Column('demo', sa.Boolean(), nullable=False,
                                         server_default=sa.false()))

    op.create_table('setores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('sigla', sa.String(length=10), nullable=True),
        sa.Column('hospital_id', sa.Integer(), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(['hospital_id'], ['hospitais.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.add_column('atendimentos', sa.Column('setor_id', sa.Integer(), nullable=True))
    op.add_column('atendimentos', sa.Column('protocolo', sa.String(length=64), nullable=True))
    op.add_column('atendimentos', sa.Column('paciente', sa.String(length=120), nullable=True))
    op.add_column('atendimentos', sa.Column('prioridade', sa.String(length=20), nullable=False,
                                            server_default='sem_triagem'))
    op.add_column('atendimentos', sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False,
                                            server_default=sa.func.now()))
    op.create_unique_constraint('uq_atendimentos_protocolo', 'atendimentos', ['protocolo'])
    op.create_index('ix_atendimentos_hospital_status', 'atendimentos',
                    ['hospital_id', 'status'], unique=False)
    op.create_foreign_key('fk_atendimentos_setor', 'atendimentos', 'setores',
                          ['setor_id'], ['id'])

    # hora_final deixava de ser informativa por nascer preenchida; normaliza o estado atual.
    op.execute('UPDATE atendimentos SET hora_final = NULL WHERE status NOT IN (\'finalizado\', \'cancelado\')')


def downgrade():
    op.drop_constraint('fk_atendimentos_setor', 'atendimentos', type_='foreignkey')
    op.drop_index('ix_atendimentos_hospital_status', table_name='atendimentos')
    op.drop_constraint('uq_atendimentos_protocolo', 'atendimentos', type_='unique')
    op.drop_column('atendimentos', 'atualizado_em')
    op.drop_column('atendimentos', 'prioridade')
    op.drop_column('atendimentos', 'paciente')
    op.drop_column('atendimentos', 'protocolo')
    op.drop_column('atendimentos', 'setor_id')
    op.drop_table('setores')
    op.drop_column('hospitais', 'demo')
