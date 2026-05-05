# arquivo: services/auditoria.py
import pandas as pd
import io
import base64

def rodar_auditoria_completa(dados_bdt, dados_combustivel):
    alertas = []
    logs_bdt = []
    km_total_declarado = 0
    km_total_nao_registrado = 0
    
    km_out_anterior = None

    for i, linha in enumerate(dados_bdt):
        dia = int(linha['dia'])
        origem = linha['origem'].upper()
        destino = linha['destino'].upper()
        km_in = float(linha['km_in'])
        km_out = float(linha['km_out'])
        
        distancia = km_out - km_in
        km_total_declarado += distancia
        
        # REGRA 1
        if km_out < km_in:
            alertas.append(f"🔴 Erro no DIA {dia}: KM Final ({km_out}) é menor que o KM Inicial ({km_in}) de {origem} para {destino}.")
            
        # REGRAS 2 e 3
        if km_out_anterior is not None:
            salto = km_in - km_out_anterior
            
            if salto > 0:
                km_total_nao_registrado += salto
                alertas.append(f"🟡 Salto não registrado de {salto:.1f}km antes da viagem do DIA {dia} ({km_out_anterior} -> {km_in}).")
                
                for comb in dados_combustivel:
                    km_bomba = float(comb['km_bomba'])
                    if km_out_anterior < km_bomba < km_in:
                        alertas.append(f"🚨 FRAUDE GRAVE: Abastecimento de {comb['litros']}L no KM {km_bomba} ocorreu durante o trajeto não registrado de {salto:.1f}km!")

        # REGRA 4 (CORRIGIDA)
        for comb in dados_combustivel:
            dia_comb = int(comb['dia'])
            km_bomba = float(comb['km_bomba'])
            
            # Agora verifica apenas se o abastecimento for de um dia anterior (<)
            if dia_comb < dia and km_bomba > km_in:
                alertas.append(f"🚨 INCONSISTÊNCIA DE HODÔMETRO: No DIA {dia}, BDT iniciou em {km_in}, mas um abastecimento em dia anterior (Dia {dia_comb}) já marcava {km_bomba}.")

        km_out_anterior = km_out
        
        logs_bdt.append({
            "Dia": dia, "Origem": origem, "Destino": destino, 
            "KM Inicial": km_in, "KM Final": km_out, "Distância (km)": distancia
        })

    df_bdt = pd.DataFrame(logs_bdt)
    df_comb = pd.DataFrame(dados_combustivel)
    df_alertas = pd.DataFrame({"Alertas Encontrados": alertas})
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_bdt.to_excel(writer, sheet_name='BDT Validado', index=False)
        if not df_comb.empty:
            df_comb.to_excel(writer, sheet_name='Abastecimentos', index=False)
        df_alertas.to_excel(writer, sheet_name='Alertas', index=False)
    
    excel_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return {
        "status": "sucesso",
        "km_declarado": km_total_declarado,
        "km_nao_registrado": km_total_nao_registrado,
        "total_rodado": km_total_declarado + km_total_nao_registrado,
        "alertas": alertas,
        "excel_b64": excel_b64
    }