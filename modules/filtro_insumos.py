from tkinter import Toplevel, Entry, Listbox, Button, END, Label
from config.utils import ejecutar_sql
from config.db import get_connections

def seleccionar_insumo(parent):
    """
    Abre una ventana para buscar y seleccionar un insumo.
    Retorna (idarticulo, descripcion)
    """

    resultado = {"valor": None}

    win = Toplevel(parent)
    win.title("Buscar Insumo")
    win.geometry("400x400")

    Label(win, text="Buscar por código o nombre:").pack(pady=5)

    entry = Entry(win, width=40)
    entry.pack(pady=5)

    lista = Listbox(win, width=60, height=15)
    lista.pack(pady=10)

    conn_sig, cur_sig, _, _ = get_connections()

    def buscar():
        texto = entry.get().strip()

        query = f"""
        SELECT idarticulos, descrip1
        FROM articulos
        WHERE idarticulos LIKE '%{texto}%'
           OR descrip1 LIKE '%{texto}%'
        LIMIT 100
        """

        cur_sig.execute(query)
        resultados = cur_sig.fetchall()

        lista.delete(0, END)

        for r in resultados:
            lista.insert(END, f"{r['idarticulos']} - {r['descrip1']}")

    def seleccionar():
        sel = lista.curselection()
        if not sel:
            return

        texto = lista.get(sel[0])
        idart = texto.split(" - ")[0]
        desc = texto.split(" - ")[1]

        resultado["valor"] = (idart, desc)
        win.destroy()

    Button(win, text="Buscar", command=buscar).pack()
    Button(win, text="Seleccionar", command=seleccionar).pack(pady=5)

    win.wait_window()

    return resultado["valor"]