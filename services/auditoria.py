import pandas as pd
import io
import base64
from datetime import datetime, timedelta

# =========================================================================
# 1. PAINEL DE CONTROLE (MARGENS E TOLERÂNCIAS)
# =========================================================================
CONFIGURACOES = {
    "margem_km_erro_digitação": 1.0,     # Até 1km negativo pode ser perdoado como erro visual do painel
    "margem_km_salto_aceitavel": 5.0,    # Até 5km de salto perdoados (estacionamento, volta na quadra)
    "margem_minutos_jornada": 120,       # Tolerância antes das 08h ou depois das 18h (em minutos)
    "horas_trabalho_dia": 8.0,           # Meta de horas por dia
    "horas_extra_limite": 2.0,           # Acima de 10h (8+2) o sistema reclama de jornada excessiva
    "margem_minutos_posto": 15,          # Diferença aceitável entre o relógio da bomba e do carro
    "consumo_esperado_km_l": 10.0,       # Consumo médio esperado do veículo (Ex: 10 km por litro)
    "margem_tolerancia_consumo": 2.5,    # Aceita oscilar entre 7.5 km/L e 12.5 km/L (trânsito, ar condicionado)
    
    # NOVA CONFIGURAÇÃO DE VELOCIDADE
    "velocidade_maxima_permitida_kmh": 200.0 # Velocidade média máxima aceitável antes de considerar Inconsistencia ou erro
}

# =========================================================================
# 2. DICIONÁRIO DE TEXTOS (DOCUMENTAÇÃO DAS REGRAS)
# =========================================================================
TEXTOS_AUDITORIA = {
    "ERR-KM01": {
        "titulo": "🔴 [ERR-KM01] Hodômetro Negativo",
        "detalhe": "O KM final registrado é menor que o KM inicial. Verificar se foi preenchido corretamente pelo motorista ou se houve erro de digitação ao passar para a planilha."
    },
    "ERR-TMP01": {
        "titulo": "🔴 [ERR-TMP01] Tempo Negativo",
        "detalhe": "A hora final da corrida é anterior à hora inicial (e não se enquadra em virada de dia). Verificar se as horas foram anotadas na ordem correta."
    },
    "ALT-JRN01": {
        "titulo": "🟡 [ALT-JRN01] Fora do Horário",
        "detalhe": "A viagem ocorreu fora da janela das 08:00 às 18:00. Verificar se a hora extra ou deslocamento foi devidamente autorizado pela gestão."
    },
    "ALT-JRN02": {
        "titulo": "🟡 [ALT-JRN02] Jornada Diária Excessiva",
        "detalhe": "O tempo total entre a primeira e a última viagem do dia ultrapassou o limite de horas normais de trabalho estabelecidas. Verificar se houve autorização para horas extras."
    },
    "ALT-SLT01": {
        "titulo": "🟡 [ALT-SLT01] Salto de Hodômetro Não Registrado",
        "detalhe": "Existe uma quilometragem faltante entre o fim da última viagem e o início desta. Pode indicar uso do veículo para fins pessoais ou esquecimento de registro, não é necessariamente um problema, mas merece atenção para entender o motivo do salto."
    },
    "INC-ABS01": {
        "titulo": "🚨 [INC-ABS01] Abastecimento durante Salto",
        "detalhe": "Um abastecimento com o cartão de recarga foi detectado exatamente no intervalo de um salto não registrado do BDT. Pode indicar que o motorista abasteceu durante um trajeto que não foi declarado, que adulterou o hodômetro no preenchimento ou que fez a recarga para dias seguintes. Verificar se o motorista consumiu durante o salto.Qualquer combustível gasto durante um salto deve ser reposto pelo motorista, já que indica uso pessoal do veículo."
    },
    "INC-ABS02": {
        "titulo": "🚨 [INC-ABS02] Inconsistência de Horário",
        "detalhe": "A QUILOMETRAGEM do hodômetro do abastecimento condiz com uma das viagens do bdt, mas a HORA do abastecimento ocorreu fora da janela de tempo em que essa mesma viagem aconteceu. Indica adulteração do horário ou do hodômetro. Verificar se o motorista tem justificativa para essa inconsistência, ou se preencheu o bdt incorretamente."
    },
    "INC-CNS01": {
        "titulo": "🚨 [INC-CNS01] Consumo Anômalo de Combustível",
        "detalhe": "A média de consumo calculada (KM/L) destoa da capacidade do veículo e da margem aceitável. Consumo excessivo indica possível desvio de combustível. Economia irreal indica viagens omitidas ou abastecimentos pagos por fora."
    },
    "INC-VEL01": {
        "titulo": "🚨 [INC-VEL01] Velocidade Média Impossível",
        "detalhe": "A velocidade média calculada para o trajeto ultrapassa o limite físico configurado, indicando erro grave na anotação do tempo da viagem, erro de digitação ou adulteração de hodômetro."
    }
}

def criar_alerta(codigo, resumo):
    return {
        "codigo": codigo,
        "titulo": TEXTOS_AUDITORIA[codigo]["titulo"],
        "resumo": resumo,
        "detalhe": TEXTOS_AUDITORIA[codigo]["detalhe"]
    }

# =========================================================================
# 3. MOTOR DA AUDITORIA
# =========================================================================
def rodar_auditoria_completa(dados_bdt, dados_combustivel):
    alertas = []
    logs_bdt = []
    km_total_declarado = 0
    km_total_nao_registrado = 0
    
    # Variáveis para a nova caixa de resumo geral
    distancia_util_velocidade = 0
    tempo_util_velocidade = 0
    consumo_real = 0
    
    viagem_anterior = None
    jornada_diaria = {} # Para calcular as horas trabalhadas no dia

    for i, linha in enumerate(dados_bdt):
        dia = int(linha['dia'])
        origem, destino = linha['origem'].upper(), linha['destino'].upper()
        km_in, km_out = float(linha['km_in']), float(linha['km_out'])
        distancia = km_out - km_in
        km_total_declarado += distancia

        try:
            h_in = datetime.strptime(linha['hora_in'], "%H:%M").time()
            h_out = datetime.strptime(linha['hora_out'], "%H:%M").time()
            
            data_in = datetime(2026, 1, dia, h_in.hour, h_in.minute)
            data_out = datetime(2026, 1, dia, h_out.hour, h_out.minute)
            
            if data_out < data_in:
                data_out += timedelta(days=1)
                
            valido_tempo = True
        except:
            valido_tempo = False

        if distancia < -CONFIGURACOES["margem_km_erro_digitação"]:
            alertas.append(criar_alerta("ERR-KM01", f"No DIA {dia}, KM de {origem} a {destino} está negativo ({km_in} para {km_out})."))

        if valido_tempo:
            
            if distancia > 0:
                horas_viagem = (data_out - data_in).total_seconds() / 3600.0
                if horas_viagem > 0:
                    # Somando para a média geral que vai aparecer na tela
                    distancia_util_velocidade += distancia
                    tempo_util_velocidade += horas_viagem
                    
                    velocidade_media = distancia / horas_viagem
                    if velocidade_media > CONFIGURACOES["velocidade_maxima_permitida_kmh"]:
                        minutos_viagem = horas_viagem * 60
                        alertas.append(criar_alerta("INC-VEL01", f"No DIA {dia}, trajeto de {origem} a {destino} cobriu {distancia:.1f}km em apenas {minutos_viagem:.0f} minutos. Velocidade média: {velocidade_media:.1f} km/h!"))
                elif horas_viagem == 0:
                    alertas.append(criar_alerta("INC-VEL01", f"No DIA {dia}, trajeto de {origem} a {destino} cobriu {distancia:.1f}km em 0 minutos (Hora Inicio e Hora Fim são iguais). Velocidade infinita!"))

            if dia not in jornada_diaria:
                jornada_diaria[dia] = {"primeiro_in": data_in, "ultimo_out": data_out}
            else:
                jornada_diaria[dia]["ultimo_out"] = data_out

            inicio_comercial = datetime(data_in.year, data_in.month, data_in.day, 8, 0)
            fim_comercial = datetime(data_out.year, data_out.month, data_out.day, 18, 0)
            
            if data_in < inicio_comercial - timedelta(minutes=CONFIGURACOES["margem_minutos_jornada"]):
                alertas.append(criar_alerta("ALT-JRN01", f"Viagem DIA {dia} iniciou às {h_in.strftime('%H:%M')}."))
            if data_out > fim_comercial + timedelta(minutes=CONFIGURACOES["margem_minutos_jornada"]):
                alertas.append(criar_alerta("ALT-JRN01", f"Viagem DIA {dia} encerrou às {h_out.strftime('%H:%M')}."))

        if viagem_anterior is not None:
            salto = km_in - viagem_anterior['km_out']
            
            if salto > CONFIGURACOES["margem_km_salto_aceitavel"]:
                km_total_nao_registrado += salto
                alertas.append(criar_alerta("ALT-SLT01", f"Salto de {salto:.1f}km entre a viagem passada e o início da viagem do DIA {dia}."))
                
                for comb in dados_combustivel:
                    km_bomba = float(comb['km_bomba'])
                    if viagem_anterior['km_out'] < km_bomba < km_in:
                        alertas.append(criar_alerta("INC-ABS01", f"Abastecimento de {comb['litros']}L no DIA {comb['dia']} (KM {km_bomba}) no meio do salto não registrado de {salto:.1f}km!"))

        if valido_tempo:
            for comb in dados_combustivel:
                if comb['hora'] and comb['dia'] == str(dia):
                    km_bomba = float(comb['km_bomba'])
                    
                    if km_in <= km_bomba <= km_out:
                        try:
                            h_comb_obj = datetime.strptime(comb['hora'], "%H:%M").time()
                            data_comb = datetime(data_in.year, data_in.month, data_in.day, h_comb_obj.hour, h_comb_obj.minute)
                            
                            if data_comb < data_in and (data_out - data_in).days > 0:
                                data_comb += timedelta(days=1)
                            
                            janela_in = data_in - timedelta(minutes=CONFIGURACOES["margem_minutos_posto"])
                            janela_out = data_out + timedelta(minutes=CONFIGURACOES["margem_minutos_posto"])
                            
                            if not (janela_in <= data_comb <= janela_out):
                                alertas.append(criar_alerta("INC-ABS02", f"No DIA {dia}, trajeto condiz com abastecimento, mas viagem ocorreu {h_in.strftime('%H:%M')}-{h_out.strftime('%H:%M')} e o posto registrou {comb['hora']}."))
                        except:
                            pass

        viagem_anterior = {'km_out': km_out, 'valido_tempo': valido_tempo, 'data_out': data_out if valido_tempo else None}
        logs_bdt.append({"Dia": dia, "Hora In": linha['hora_in'], "Hora Fim": linha['hora_out'], "Origem": origem, "Destino": destino, "KM Inicial": km_in, "KM Final": km_out, "Distância (km)": distancia})

    limite_horas = CONFIGURACOES["horas_trabalho_dia"] + CONFIGURACOES["horas_extra_limite"]
    for dia_jornada, dados_jornada in jornada_diaria.items():
        horas_trabalhadas = (dados_jornada["ultimo_out"] - dados_jornada["primeiro_in"]).total_seconds() / 3600.0
        if horas_trabalhadas > limite_horas:
            alertas.append(criar_alerta("ALT-JRN02", f"No DIA {dia_jornada}, o motorista acumulou uma jornada total de {horas_trabalhadas:.1f} horas."))

    # Cálculos Finais para o Painel Geral
    velocidade_media_geral = 0
    if tempo_util_velocidade > 0:
        velocidade_media_geral = distancia_util_velocidade / tempo_util_velocidade

    total_litros = sum(float(comb['litros']) for comb in dados_combustivel if comb.get('litros'))
    if len(dados_bdt) > 0:
        km_absoluto_inicial = float(dados_bdt[0]['km_in'])
        km_absoluto_final = float(dados_bdt[-1]['km_out'])
        distancia_total_mes = km_absoluto_final - km_absoluto_inicial
        
        if total_litros > 0 and distancia_total_mes > 0:
            consumo_real = distancia_total_mes / total_litros
            consumo_esp = CONFIGURACOES["consumo_esperado_km_l"]
            margem = CONFIGURACOES["margem_tolerancia_consumo"]
            
            if consumo_real < (consumo_esp - margem):
                alertas.append(criar_alerta("INC-CNS01", f"Veículo fez apenas {consumo_real:.1f} KM/L (Esperado: ~{consumo_esp} KM/L). Desvio ou extração de combustível provável."))
            elif consumo_real > (consumo_esp + margem):
                alertas.append(criar_alerta("INC-CNS01", f"Veículo fez irrealistas {consumo_real:.1f} KM/L (Esperado: ~{consumo_esp} KM/L). Notas de abastecimento foram omitidas ou apagadas."))

    # =========================================================================
    # GERAÇÃO DO EXCEL PROFISSIONAL (COM RESUMO E FORMATAÇÃO)
    # =========================================================================
    df_bdt = pd.DataFrame(logs_bdt)
    df_comb = pd.DataFrame(dados_combustivel)
    
    # Transforma os alertas que estão em dicionário para um formato de tabela
    if alertas:
        df_alertas = pd.DataFrame([{
            "Grau": "🔴 Erro" if "🔴" in a["titulo"] else "🚨 Inconsistência" if "🚨" in a["titulo"] else "🟡 Alerta",
            "Código": a["codigo"],
            "Descrição": a["titulo"].replace("🔴 ", "").replace("🚨 ", "").replace("🟡 ", ""),
            "Ocorrência": a["resumo"],
            "Ação Recomendada": a["detalhe"]
        } for a in alertas])
    else:
        df_alertas = pd.DataFrame(columns=["Grau", "Código", "Descrição", "Ocorrência", "Ação Recomendada"])
    
    # Cria a aba de Resumo Geral
    df_resumo = pd.DataFrame({
        "Indicador": ["Distância Declarada (BDT)", "Distância Omitida (Saltos)", "Total Rodado Real", "Velocidade Média Geral", "Consumo Médio Calculado"],
        "Valor": [
            f"{km_total_declarado:.1f} km", 
            f"{km_total_nao_registrado:.1f} km", 
            f"{(km_total_declarado + km_total_nao_registrado):.1f} km", 
            f"{velocidade_media_geral:.1f} km/h" if 'velocidade_media_geral' in locals() else "0 km/h", 
            f"{consumo_real:.1f} km/L" if 'consumo_real' in locals() else "0 km/L"
        ]
    })

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_resumo.to_excel(writer, sheet_name='Resumo Diretoria', index=False)
        df_alertas.to_excel(writer, sheet_name='Alertas Detalhados', index=False)
        df_bdt.to_excel(writer, sheet_name='BDT Validado', index=False)
        if not df_comb.empty:
            df_comb.to_excel(writer, sheet_name='Abastecimentos', index=False)
        
        # O pulo do gato: Acessar a planilha gerada para esticar as colunas automaticamente!
        workbook = writer.book
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            for col in worksheet.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 4)
                # Trava um limite máximo para textos muito grandes (como a Ação Recomendada) não quebrarem a tela
                worksheet.column_dimensions[column].width = min(adjusted_width, 80) 

    excel_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return {
        "status": "sucesso",
        "km_declarado": km_total_declarado,
        "km_nao_registrado": km_total_nao_registrado,
        "total_rodado": km_total_declarado + km_total_nao_registrado,
        "velocidade_media": velocidade_media_geral if 'velocidade_media_geral' in locals() else 0,
        "consumo": consumo_real if 'consumo_real' in locals() else 0,
        "alertas": alertas,
        "excel_b64": excel_b64
    }