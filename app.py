import ttkbootstrap as tb
from gui.login_window import mostrar_login
from gui.main_window import iniciar_en_root

if __name__ == "__main__":
    root = tb.Window(themename="superhero")
    root.withdraw()   # oculto hasta que el login sea exitoso

    _user = [None]
    mostrar_login(root, on_success=lambda u: _user.__setitem__(0, u))

    if _user[0] is not None:
        iniciar_en_root(root, user_info=_user[0])
        root.mainloop()
    else:
        root.destroy()
