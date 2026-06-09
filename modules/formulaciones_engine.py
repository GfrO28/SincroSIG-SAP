# modules/formulaciones_engine.py

import time

BASE_TIENDA = 3  # Tienda de referencia para comparar diferencias


def construir_dataset_formulaciones(
    articulos,
    tiendas,
    tipo_por_tienda,
    base_por_tipo,
    cache_idforms,
    cache_detalles,
    cur_val,
    get_store_connection,
    obtener_detalle_formulacion,
    articulo_valido_para_formulacion,
    progress_callback=None
):

    total = len(articulos)
    cache_conexiones = {}

    def get_conn(tda):
        if tda not in cache_conexiones:
            cache_conexiones[tda] = get_store_connection(tda)
        return cache_conexiones[tda]

    resultados = []

    for idx, idart in enumerate(articulos, start=1):

        try:
            if progress_callback:
                progress_callback(
                    (idx / total) * 100,
                    f"Procesando artículo {idx}/{total}"
                )

            print(f"\nENGINE: idart={idart}")

            valido = articulo_valido_para_formulacion(cur_val, idart, {})
            if not valido:
                print(f"SKIP PRECIART idart={idart}")

            # ==========================================
            # LOOP TIENDAS → detalles_por_tienda
            # ==========================================
            detalles_por_tienda = {}   # {tda: {idinsumo: {insumo, cantidad, unidad, almacen}}}
            descripcion_formula = None

            for tda in list(tiendas):

                print(f"ENGINE: idart={idart} tda={tda}")
                print(f"  → detalles_por_tienda tiendas con data: {list(detalles_por_tienda.keys())}")
                # for tda_debug, det_debug in detalles_por_tienda.items():
                #     print(f"     tda={tda_debug} insumos={list(det_debug.keys())[:5]}...")  # primeros 5


                # --- Obtener idformulacion desde cache ---
                idform = None
                if isinstance(cache_idforms, dict):
                    idform = cache_idforms.get((int(idart), int(tda)))
                    if idform is None:
                        idform = cache_idforms.get(int(idart))

                if not idform:
                    continue

                # BUG 1 CORREGIDO:
                # El cache_detalles usa str(idformulacion) como clave simple,
                # no una tupla (tda, idform). idformulacion es str (p.ej. '79-3-052011').
                cache_key = str(idform)

                # --- Buscar en cache de detalles ---
                if cache_key in cache_detalles:
                    info = cache_detalles[cache_key]
                    detalles_por_tienda[int(tda)] = info["detalles"]
                    descripcion_formula = descripcion_formula or info.get("descripcion")
                    continue

                # --- Fallback: consultar DB de tienda ---
                try:
                    conn, cur = get_conn(tda)
                    detalle, desc = obtener_detalle_formulacion(cur, idform)

                    if detalle:
                        detalles_por_tienda[int(tda)] = detalle
                        descripcion_formula = descripcion_formula or desc

                except Exception as e:
                    print(f"ERROR TDA {tda}: {e}")

                finally:
                    time.sleep(0.01)

            # ==========================================
            # Sin formulaciones en ninguna tienda → skip
            # ==========================================
            if not detalles_por_tienda:
                print(f"ARTICULO SIN FORMULACIONES EN TIENDAS: {idart}")
                continue

            # ==========================================
            # BUG 3 + 4 CORREGIDOS:
            # Construir insumos con nombre/unidad/almacen
            # y calcular tiene_diferencias vs tienda base.
            # ==========================================
            insumos_union = sorted(
                {k for d in detalles_por_tienda.values() for k in d.keys()}
            )
            print(f"  → insumos_union: {insumos_union[:10]}...")  # primeros 10

            # Referencia de nombre/unidad/almacen: buscar en bases disponibles (3, 34, 41)
            ref_base = None
            for base_tda in base_por_tipo.values():
                ref_base = detalles_por_tienda.get(base_tda)
                if ref_base:
                    break
            if not ref_base:
                ref_base = next(iter(detalles_por_tienda.values()), {})

            print(f"  → ref_base encontrada en tda base: {ref_base is not None}, keys: {list(ref_base.keys())[:5] if ref_base else 'VACÍO'}")

            insumos = []
            tiene_diferencias = False

            for id_ins in insumos_union:                

                ref = ref_base.get(id_ins) or next(
                    (d[id_ins] for d in detalles_por_tienda.values() if id_ins in d),
                    {}
                )
                print(f"    id_ins={id_ins}, ref={ref}")

                nombre      = ref.get("insumo", "")
                unidad_ref  = ref.get("unidad", "")
                almacen_ref = ref.get("almacen", "")

                tiendas_data = {}

                for tda in tiendas:

                    det = detalles_por_tienda.get(int(tda), {}).get(id_ins)

                    # Base según tipo de ESTA tienda → dentro del loop de tda
                    tipo     = tipo_por_tienda.get(int(tda))
                    base_tda = base_por_tipo.get(tipo)
                    det_base = (
                        detalles_por_tienda.get(base_tda, {}).get(id_ins)
                        if base_tda is not None else None
                    )

                    if det:
                        if det_base:
                            diff = (
                                det.get("cantidad") != det_base.get("cantidad")
                                or det.get("unidad", "")  != det_base.get("unidad", "")
                                or det.get("almacen", "") != det_base.get("almacen", "")
                            )
                        else:
                            diff = False
                        if diff:
                            tiene_diferencias = True
                        
                        tiendas_data[int(tda)] = {
                            "cantidad": det.get("cantidad"),
                            "unidad":   det.get("unidad", ""),
                            "almacen":  det.get("almacen", ""),
                            "diff": diff
                        }
                        # if det and det_base:
                        #     print(f"      tda={tda} det={det} | det_base={det_base} | diff={diff}")
                        # elif det and not det_base:
                        #     print(f"      tda={tda} det={det} | SIN BASE (tipo={tipo}, base_tda={base_tda})")
                    else:
                        tiendas_data[int(tda)] = {
                            "cantidad": None,
                            "unidad":   "",
                            "almacen":  "", 
                            "diff": False
                        }

                insumos.append({
                    "idinsumo":     id_ins,
                    "nombre":       nombre,
                    "unidad":       unidad_ref,
                    "almacen_base": almacen_ref,
                    "tiendas":      tiendas_data,
                })

            print(f"  → tiene_diferencias={tiene_diferencias}")
            # for ins in insumos:
            #     diffs = {tda: v for tda, v in ins["tiendas"].items() if v["diff"]}
            #     if diffs:
            #         print(f"     DIFF en {ins['nombre']}: {diffs}")
            resultados.append({
                "idart":             idart,
                "descripcion":       descripcion_formula or f"ART {idart}",
                "insumos":           insumos,
                "tiene_diferencias": tiene_diferencias,
            })

        except Exception as e:
            import traceback
            print(f"ERROR FATAL ARTICULO {idart}: {e}")
            print(traceback.format_exc())

    # ==========================================
    # Cleanup conexiones por tienda
    # ==========================================
    for conn, cur in cache_conexiones.values():
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

    print("\n=== RESUMEN ENGINE ===")
    print("INPUT:", len(articulos))
    print("OUTPUT:", len(resultados))

    # BUG 2 CORREGIDO:
    # El controller y el exportador esperan {"articulos": [...]},
    # no la lista directa.
    return {"articulos": resultados}