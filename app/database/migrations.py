from sqlalchemy import MetaData, inspect
from sqlalchemy.schema import CreateTable

from app.models import Unidade


def remover_unicidade_global_nome_unidade(engine) -> bool:
    if engine.dialect.name != "sqlite":
        return False

    nome_tabela = Unidade.__tablename__
    with engine.connect() as connection:
        inspector = inspect(connection)
        if nome_tabela not in inspector.get_table_names():
            return False

        unique_constraints = inspector.get_unique_constraints(nome_tabela)
        unique_indexes = inspector.get_indexes(nome_tabela)
        sqlite_indexes = connection.exec_driver_sql(
            f"PRAGMA index_list({inspector.engine.dialect.identifier_preparer.quote(nome_tabela)})"
        ).all()
        preparador = connection.dialect.identifier_preparer
        unique_index_columns = [
            tuple(
                coluna[2]
                for coluna in connection.exec_driver_sql(
                    f"PRAGMA index_info({preparador.quote(indice[1])})"
                ).all()
            )
            for indice in sqlite_indexes
            if indice[2]
        ]
        tem_unicidade_global = any(
            constraint.get("column_names") == ["nome"]
            for constraint in unique_constraints
        ) or any(
            index.get("unique")
            and index.get("column_names") == ["nome"]
            for index in unique_indexes
        ) or ("nome",) in unique_index_columns
        if not tem_unicidade_global:
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_unidades_nome ON unidades (nome)"
            )
            connection.commit()
            return False

        tabela_temporaria = "unidades__migrando_sem_nome_unico"
        if tabela_temporaria in inspector.get_table_names():
            raise RuntimeError(
                f"A tabela temporária {tabela_temporaria} já existe; migração cancelada."
            )

        metadata_temporaria = MetaData()
        tabela_nova = Unidade.__table__.to_metadata(
            metadata_temporaria,
            name=tabela_temporaria,
        )
        tabela_original_sql = preparador.quote(nome_tabela)
        tabela_temporaria_sql = preparador.quote(tabela_temporaria)
        colunas = [coluna.name for coluna in Unidade.__table__.columns]
        colunas_sql = ", ".join(preparador.quote(nome) for nome in colunas)

        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        try:
            with connection.begin():
                connection.exec_driver_sql(
                    str(CreateTable(tabela_nova).compile(dialect=connection.dialect))
                )
                connection.exec_driver_sql(
                    f"INSERT INTO {tabela_temporaria_sql} ({colunas_sql}) "
                    f"SELECT {colunas_sql} FROM {tabela_original_sql}"
                )
                connection.exec_driver_sql(f"DROP TABLE {tabela_original_sql}")
                connection.exec_driver_sql(
                    f"ALTER TABLE {tabela_temporaria_sql} RENAME TO {tabela_original_sql}"
                )
                connection.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_unidades_nome ON unidades (nome)"
                )
                erros_fk = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
                if erros_fk:
                    raise RuntimeError(
                        "A migração detectou referências inválidas; transação cancelada."
                    )
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()

    return True