from sqlalchemy import create_engine, inspect

from app.database.migrations import remover_unicidade_global_nome_unidade


def test_remove_unique_global_preservando_unidade_e_contato():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE unidades ("
            "id INTEGER PRIMARY KEY, "
            "nome VARCHAR(200) NOT NULL UNIQUE, "
            "categoria VARCHAR(100) NOT NULL, "
            "comarca VARCHAR(120), descricao TEXT, endereco TEXT, "
            "email VARCHAR(254), ativo BOOLEAN NOT NULL, "
            "criado_em DATETIME NOT NULL, atualizado_em DATETIME NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE contatos ("
            "id INTEGER PRIMARY KEY, unidade_id INTEGER NOT NULL "
            "REFERENCES unidades(id), tipo VARCHAR(50) NOT NULL, "
            "valor VARCHAR(100) NOT NULL, descricao VARCHAR(255), "
            "principal BOOLEAN NOT NULL, ativo BOOLEAN NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE competencias_unidade ("
            "id INTEGER PRIMARY KEY, unidade_id INTEGER NOT NULL "
            "REFERENCES unidades(id) ON DELETE CASCADE, nome VARCHAR(255) NOT NULL, "
            "ativo BOOLEAN NOT NULL, criado_em DATETIME NOT NULL, "
            "UNIQUE(unidade_id, nome))"
        )
        connection.exec_driver_sql(
            "INSERT INTO unidades VALUES (?, ?, ?, ?, NULL, NULL, NULL, 1, ?, ?)",
            (7, "1ª Vara Cível", "Varas Cíveis", "São Luís", "2026-01-01", "2026-01-01"),
        )
        connection.exec_driver_sql(
            "INSERT INTO contatos VALUES (?, ?, ?, ?, NULL, 1, 1)",
            (9, 7, "ramal", "2549"),
        )
        connection.exec_driver_sql(
            "INSERT INTO competencias_unidade VALUES (?, ?, ?, 1, ?)",
            (11, 7, "Saúde Pública", "2026-01-01"),
        )

    assert remover_unicidade_global_nome_unidade(engine) is True
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql(
            "INSERT INTO unidades VALUES (?, ?, ?, ?, NULL, NULL, NULL, 1, ?, ?)",
            (8, "1ª Vara Cível", "Varas Cíveis", "Balsas", "2026-01-01", "2026-01-01"),
        )
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql(
            "SELECT unidade_id, valor FROM contatos"
        ).all() == [(7, "2549")]
        assert connection.exec_driver_sql(
            "SELECT unidade_id, nome FROM competencias_unidade"
        ).all() == [(7, "Saúde Pública")]
        assert connection.exec_driver_sql(
            "SELECT id, nome, comarca FROM unidades ORDER BY id"
        ).all() == [
            (7, "1ª Vara Cível", "São Luís"),
            (8, "1ª Vara Cível", "Balsas"),
        ]

    assert remover_unicidade_global_nome_unidade(engine) is False
    assert inspect(engine).get_unique_constraints("unidades") == []
    assert any(
        index["name"] == "ix_unidades_nome"
        for index in inspect(engine).get_indexes("unidades")
    )
    engine.dispose()