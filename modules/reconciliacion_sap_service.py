# modules/ reconciliacion_sap_service.py

import pandas as pd
import io
import json


def procesar_data_sap_clipboard():
    """
    Lee la tabla copiada de SAP desde el portapapeles y la limpia.
    """
    try:
        # SAP usa tabulaciones (\t) al copiar su grid
        df = pd.read_clipboard(sep='\t')
        
        # Limpieza de nombres de columnas (quitar espacios o caracteres raros)
        df.columns = [c.strip() for c in df.columns]
        
        # Limpieza de números: SAP suele poner comas en miles '-1,176.00'
        cols_numericas = ['Stock_A_Fecha']
        for col in cols_numericas:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '').astype(float)
        
        return df
    except Exception as e:
        raise Exception(f"Error al leer el portapapeles: {e}")

def calcular_ajustes_tres_vias(df_sap, df_logs, df_saldos):
    """
    Calcula nivelación y cola de migración incluyendo ID de movimiento para trazabilidad.
    """
    registros_ajuste = []

    for _, row_sap in df_sap.iterrows():
        item = str(row_sap['ItemCode'])
        whs_sap = str(row_sap['WhsCode'])
        stk_sap_inicial = float(row_sap['Stock_A_Fecha'])
        descripcion = str(row_sap.get('Descripcion', ''))
        
        # SIG: saldo por (item, whs) para NIVELACIÓN
        match_sig    = df_saldos[(df_saldos['ItemCode'] == item) & (df_saldos['WhsCode'] == whs_sap)]
        stk_sig_real = 0.0
        id_sig_niv   = "N/A"
        if not match_sig.empty:
            s_sig        = match_sig.iloc[0]
            stk_sig_real = float(s_sig['saldoinicial']) + float(s_sig['ingresos']) - float(s_sig['salidas'])
            id_sig_niv   = s_sig['idtienda']

        # COLA: match directo por (item, whs) — sin dependencia de saldos
        # Esto garantiza que TODAS las salidas fallidas del ítem en ese almacén se procesan
        logs_item = df_logs[
            (df_logs['item'] == item) &
            (df_logs['whs']  == whs_sap)
        ].sort_values('fecha')

        # Si no hay saldo pero sí hay logs, inferir tienda del primer log
        if id_sig_niv == "N/A" and not logs_item.empty:
            try:
                id_sig_niv = str(int(logs_item.iloc[0]['id_sig']))
            except (ValueError, TypeError):
                pass

        fecha_base = str(logs_item.iloc[0]['fecha']) if not logs_item.empty else "SIN FECHA"

        # --- FASE A: NIVELACIÓN ---
        stk_simulado = stk_sap_inicial
        if stk_sig_real > stk_sap_inicial:
            dif = stk_sig_real - stk_sap_inicial
            registros_ajuste.append({
                'ItemCode': item, 'ID_SIG': id_sig_niv, 'Fecha': fecha_base,
                'WhsCode': whs_sap, 'Concepto': 'NIVELACIÓN (Sincronizar con SIG)',
                'Stock_A_Fecha': stk_sap_inicial, 'Stock_SIG': stk_sig_real,
                'Movimiento': 0.00, 'Monto_A_Ingresar': dif, 'Prioridad': 0,
                'ID_Movimiento': 'N/A', 'Descripcion': descripcion,
            })
            stk_simulado = stk_sig_real

        # --- FASE B: COLA DE MIGRACIÓN ---
        # Cada entrada de log = una salida fallida real; se acumulan en orden cronológico
        for _, log in logs_item.iterrows():
            cant_salida = round(float(log['qty']), 4)
            is_primary  = bool(log.get('is_primary', True))
            try:
                id_sig_log = str(int(log['id_sig'])) if 'id_sig' in log else id_sig_niv
            except (ValueError, TypeError):
                id_sig_log = id_sig_niv
            monto_inyectar = 0.0
            stk_sim_r = round(stk_simulado, 4)
            if stk_sim_r < cant_salida:
                monto_inyectar = round(cant_salida - stk_sim_r, 4)
                stk_simulado  += monto_inyectar

            registros_ajuste.append({
                'ItemCode': item, 'ID_SIG': id_sig_log, 'Fecha': str(log['fecha']),
                'WhsCode': whs_sap, 'Concepto': 'COLA DE MIGRACIÓN (Salida Fallida)',
                'Stock_A_Fecha': stk_sap_inicial, 'Stock_SIG': stk_sig_real,
                'Movimiento': cant_salida, 'Monto_A_Ingresar': monto_inyectar,
                'Prioridad': 1,
                'ID_Movimiento': log.get('id_mov', 'N/A'),
                'Is_Primary': is_primary,
                'Descripcion': descripcion,
            })
            stk_simulado = round(stk_simulado - cant_salida, 4)

    return pd.DataFrame(registros_ajuste)