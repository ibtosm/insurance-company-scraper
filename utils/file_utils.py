from datetime import datetime
from pathlib import Path


# -----------------------------
# ファイルバックアップ
# -----------------------------
def backup_file(path: Path) -> Path:
    """
    指定ファイルが存在する場合、日付付きでバックアップを作成する。
    戻り値: バックアップファイルの Path（存在しない場合は None）
    """

    backup_name: str = f"{path.stem}_{datetime.now():%Y%m%d}{path.suffix}"
    backup_path: Path = path.parent / backup_name

    if path.exists():
        path.rename(target=backup_path)
    return backup_path
