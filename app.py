import sys
from pathlib import Path
import ttkbootstrap as tb
from gui.login_window import mostrar_login
from gui.main_window import iniciar_en_root


def _icon_path() -> str:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    return str(base / "assets" / "icon.ico")


if __name__ == "__main__":
    root = tb.Window(themename="superhero")
    try:
        root.iconbitmap(_icon_path())
    except Exception:
        pass
    root.withdraw()   # oculto hasta que el login sea exitoso

    _user = [None]
    mostrar_login(root, on_success=lambda u: _user.__setitem__(0, u))

    if _user[0] is not None:
        iniciar_en_root(root, user_info=_user[0])
        root.mainloop()
    else:
        root.destroy()
