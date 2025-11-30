from src.config.settings import get_settings


def test_settings_directories_exist():
    settings = get_settings()
    assert settings.paths.data_dir.exists()
    assert settings.paths.chroma_db.exists()
    assert settings.paths.duckdb.parent.exists()
    assert settings.paths.input_dir.exists()
    assert settings.paths.output_dir.exists()
    assert settings.paths.logs_dir.exists()
