"""
Gerador de Simulado Focado MCD Level 2 (MuleSoft Certified Developer II)
com saída otimizada em EPUB para telas e-ink compactas (ex: Xteink X4).
"""

import os
import re
import html
import json
import time
import urllib.request
from typing import List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from ebooklib import epub

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# 1. Definição da Estrutura de Saída (Structured Outputs)
class Questao(BaseModel):
    secao: str = Field(description="Nome da seção do exame MCD Level 2")
    enunciado: str = Field(description="Cenário técnico detalhado no estilo da prova MuleSoft")
    codigo_xml_ou_dw: str = Field(default="", description="Trecho curto de XML, pom.xml ou DataWeave se aplicável")
    alternativas: List[str] = Field(description="4 alternativas (A, B, C, D)")
    resposta_correta: str = Field(description="Letra e texto da alternativa correta")
    explicacao_oficial: str = Field(description="Explicação técnica baseada na doc oficial da MuleSoft")
    url_referencia: str = Field(description="Link da documentação oficial ou referência utilizada")


class BancoQuestoes(BaseModel):
    questoes: List[Questao]


# 2. Configuração de Pesos Baseada no seu Resultado
# Quanto menor a nota, maior a quantidade de questões geradas
SECOES_PESOS = [
    {
        "nome": "Implement Maintainable and Modular Mule Applications and Their Maven Build",
        "nota": "47%",
        "qtd_questoes": 12,
        "foco": "Mule Maven Plugin, parent POM, BOM (Bill of Materials), MUnit coverage/assertions, shared libraries/domains, externalized properties, exchange deployment."
    },
    {
        "nome": "Implement Performant and Reliable Mule Applications",
        "nota": "50%",
        "qtd_questoes": 12,
        "foco": "Object Store v2 (OSv2) concurrency/TTL, Idempotent Message Validator, VM queues vs Anypoint MQ, Scatter-Gather error handling, Parallel For Each, Streaming strategies, Caching scope, Until Successful."
    },
    {
        "nome": "Secure Data at Rest and In Transit",
        "nota": "67%",
        "qtd_questoes": 7,
        "foco": "Secure Configuration Properties (Blowfish/AES), TLS 1.2/1.3 one-way e two-way (mTLS) Keystore/Truststore, Cryptography module (JCE/PGP), OAuth 2.0 client credentials."
    },
    {
        "nome": "Implement Monitorable Mule Applications",
        "nota": "67%",
        "qtd_questoes": 7,
        "foco": "Custom Business Events, Correlation ID propagation (X-Correlation-Id), JSON logging, Anypoint Monitoring alerts, API Functional Monitoring, Health check endpoints."
    },
    {
        "nome": "Expose Production-Ready Anypoint Platform-Managed APIs From Mule Applications",
        "nota": "88%",
        "qtd_questoes": 2,
        "foco": "API Autodiscovery, Custom Policies, Gatekeeper, Automated Policies, RAML/OAS."
    }
]

# URLs oficiais verificadas (sempre na versão 'latest') por seção da prova
URLS_DOCS_OFICIAIS_LATEST = {
    "Implement Maintainable and Modular Mule Applications and Their Maven Build": [
        "https://docs.mulesoft.com/mule-runtime/latest/maven-reference",
        "https://docs.mulesoft.com/mule-runtime/latest/mmp-concept",
        "https://docs.mulesoft.com/mule-runtime/latest/deploy-to-cloudhub",
        "https://docs.mulesoft.com/mule-runtime/latest/shared-resources",
        "https://docs.mulesoft.com/mule-runtime/latest/configuring-properties",
        "https://docs.mulesoft.com/munit/latest/munit-maven-plugin",
        "https://docs.mulesoft.com/munit/latest/coverage-maven-concept",
        "https://docs.mulesoft.com/exchange/latest/to-publish-assets-maven",
    ],
    "Implement Performant and Reliable Mule Applications": [
        "https://docs.mulesoft.com/mule-runtime/latest/idempotent-message-validator",
        "https://docs.mulesoft.com/mule-runtime/latest/scatter-gather-concept",
        "https://docs.mulesoft.com/mule-runtime/latest/streaming-about",
        "https://docs.mulesoft.com/mule-runtime/latest/cache-scope",
        "https://docs.mulesoft.com/mule-runtime/latest/until-successful-scope",
        "https://docs.mulesoft.com/mule-runtime/latest/redelivery-policy",
        "https://docs.mulesoft.com/vm-connector/latest/",
        "https://docs.mulesoft.com/object-store/latest/osv2-guide",
    ],
    "Secure Data at Rest and In Transit": [
        "https://docs.mulesoft.com/mule-runtime/latest/secure-configuration-properties",
        "https://docs.mulesoft.com/mule-runtime/latest/safely-hiding-properties",
        "https://docs.mulesoft.com/mule-runtime/latest/tls-configuration",
        "https://docs.mulesoft.com/cryptography-module/latest/cryptography-pgp",
        "https://docs.mulesoft.com/cryptography-module/latest/cryptography-jce",
        "https://docs.mulesoft.com/http-connector/latest/http-authentication",
    ],
    "Implement Monitorable Mule Applications": [
        "https://docs.mulesoft.com/mule-runtime/latest/correlation-id",
        "https://docs.mulesoft.com/mule-runtime/latest/business-events",
        "https://docs.mulesoft.com/monitoring/latest/logs",
        "https://docs.mulesoft.com/monitoring/latest/anypoint-custom-metrics",
        "https://docs.mulesoft.com/monitoring/latest/alerts",
        "https://docs.mulesoft.com/runtime-fabric/latest/deploy-to-runtime-fabric",
        "https://docs.mulesoft.com/api-functional-monitoring/latest/bat-secret-create-task",
    ],
    "Expose Production-Ready Anypoint Platform-Managed APIs From Mule Applications": [
        "https://docs.mulesoft.com/api-manager/latest/api-autodiscovery",
        "https://docs.mulesoft.com/api-manager/latest/custom-policy",
    ],
}

MAPA_SLUGS_CANONICOS = {
    "maven-tools": "https://docs.mulesoft.com/mule-runtime/latest/maven-reference",
    "mule-maven-plugin": "https://docs.mulesoft.com/mule-runtime/latest/mmp-concept",
    "scatter-gather-component": "https://docs.mulesoft.com/mule-runtime/latest/scatter-gather-concept",
    "streaming": "https://docs.mulesoft.com/mule-runtime/latest/streaming-about",
    "vm-connector-reference": "https://docs.mulesoft.com/vm-connector/latest/",
    "cryptography-sign": "https://docs.mulesoft.com/cryptography-module/latest/cryptography-jce",
    "intro-correlation-id": "https://docs.mulesoft.com/mule-runtime/latest/correlation-id",
    "am-custom-metrics": "https://docs.mulesoft.com/monitoring/latest/anypoint-custom-metrics",
    "anypoint-custom-metrics": "https://docs.mulesoft.com/monitoring/latest/anypoint-custom-metrics",
    "health-checks": "https://docs.mulesoft.com/runtime-fabric/latest/deploy-to-runtime-fabric",
    "health-check-endpoint": "https://docs.mulesoft.com/monitoring/latest/alerts",
    "api-functional-monitoring": "https://docs.mulesoft.com/api-functional-monitoring/latest/bat-secret-create-task",
    "api-autodiscovery-concept-mule-4": "https://docs.mulesoft.com/api-manager/latest/api-autodiscovery",
    "custom-policies-configure": "https://docs.mulesoft.com/api-manager/latest/custom-policy",
    "osv2-guide": "https://docs.mulesoft.com/object-store/latest/osv2-guide",
    "to-publish-assets-maven": "https://docs.mulesoft.com/exchange/latest/to-publish-assets-maven",
}

_CACHE_URLS_VALIDADAS = {}


def normalizar_e_validar_url(url: str, secao: str) -> str:
    """
    Converte versões fixas (ex: /4.4/, /2.3/, /2.x/) para /latest/ nas URLs da MuleSoft
    e verifica se a página de documentação existe.
    """
    url_limpa = (url or "").strip().split("#")[0]

    # 1. Substitui segmentos de versão numérica (ex: /4.4/, /2.3/, /1.3/, /2.x/) por /latest/
    url_limpa = re.sub(
        r"(https://docs\.mulesoft\.com/[^/]+)/(?:v?\d+(?:\.\d+|\.x)?)/",
        r"\1/latest/",
        url_limpa,
    )

    # 2. Garante /latest/ em seções que omitiram o segmento
    url_limpa = re.sub(
        r"^https://docs\.mulesoft\.com/(exchange|monitoring|object-store|runtime-fabric|api-functional-monitoring)/(?!latest/)(.+)$",
        r"https://docs.mulesoft.com/\1/latest/\2",
        url_limpa,
    )

    # 3. Corrige slugs antigos ou redirecionados para a página oficial latest exata
    slug_final = url_limpa.rstrip("/").split("/")[-1]
    if slug_final in MAPA_SLUGS_CANONICOS:
        url_limpa = MAPA_SLUGS_CANONICOS[slug_final]

    if not url_limpa.startswith("https://docs.mulesoft.com/"):
        urls_secao = URLS_DOCS_OFICIAIS_LATEST.get(secao, [])
        return urls_secao[0] if urls_secao else "https://docs.mulesoft.com/mule-runtime/latest/"

    if url_limpa in _CACHE_URLS_VALIDADAS:
        return _CACHE_URLS_VALIDADAS[url_limpa]

    # 4. Verifica via HTTP se a URL existe (quando há conexão ativa)
    try:
        req = urllib.request.Request(
            url_limpa,
            method="HEAD",
            headers={"User-Agent": "Mozilla/5.0 (MuleSoft-Doc-Validator/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            if 200 <= resp.status < 400:
                _CACHE_URLS_VALIDADAS[url_limpa] = url_limpa
                return url_limpa
    except urllib.error.HTTPError as http_err:
        if http_err.code == 404:
            urls_secao = URLS_DOCS_OFICIAIS_LATEST.get(secao, [])
            fallback = urls_secao[0] if urls_secao else "https://docs.mulesoft.com/mule-runtime/latest/"
            _CACHE_URLS_VALIDADAS[url_limpa] = fallback
            return fallback
    except Exception:
        pass

    _CACHE_URLS_VALIDADAS[url_limpa] = url_limpa
    return url_limpa


def _limpar_json_texto(raw_text: str) -> str:
    """Remove cercas markdown ```json ... ``` caso presentes."""
    texto = raw_text.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```$", "", texto)
    return texto.strip()


def obter_modelos_candidatos(client: genai.Client, modelo_preferido: str = "gemini-3.5-flash-lite") -> List[str]:
    """
    Retorna lista ordenada de modelos priorizando Gemini 3.5 Flash Lite (500 req/dia),
    seguido de outros Flash Lite/2.5, e deixando 3.6/3.8 (20 req/dia) apenas como último recurso.
    """
    ordem_preferencia = [
        modelo_preferido,
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash-lite-preview",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash-lite-preview",
        "gemini-2.5-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
        "gemini-3.6-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.8-flash-lite",
        "gemini-3.8-flash",
    ]
    preferidos_unicos = list(dict.fromkeys(ordem_preferencia))

    try:
        modelos_api = {
            m.name.replace("models/", "") for m in client.models.list() if m.name
        }
        validos = [m for m in preferidos_unicos if m in modelos_api]
        # Outros flash-lite primeiro, depois outros flash (deixando 3.6/3.8 por último)
        extras_lite = sorted(
            [
                m for m in modelos_api
                if "flash-lite" in m.lower()
                and m not in validos
                and not any(x in m.lower() for x in ("tts", "image", "audio", "live", "thinking", "omni", "3.6", "3.8"))
            ],
            reverse=True
        )
        extras_outros = sorted(
            [
                m for m in modelos_api
                if "flash" in m.lower()
                and m not in validos
                and m not in extras_lite
                and not any(x in m.lower() for x in ("tts", "image", "audio", "live", "thinking", "omni"))
            ]
        )
        resultado = validos + extras_lite + extras_outros
        if resultado:
            return resultado
    except Exception:
        pass

    return preferidos_unicos


def _chamar_gemini_lote(
    client: genai.Client,
    secao_info: dict,
    qtd_lote: int,
    modelos_candidatos: List[str],
    enunciados_existentes: List[str],
) -> List[Questao]:
    evitar_txt = ""
    if enunciados_existentes:
        resumo_existentes = "\n".join(f"- {e[:90]}..." for e in enunciados_existentes[-10:])
        evitar_txt = f"\n    Não repita cenários já abordados nestas questões anteriores:\n{resumo_existentes}\n"

    urls_oficiais = URLS_DOCS_OFICIAIS_LATEST.get(secao_info["nome"], [])
    lista_urls_txt = "\n".join(f"      - {u}" for u in urls_oficiais)

    prompt = f"""
    Atue como um arquiteto especialista em MuleSoft certificando desenvolvedores para o exame 'Salesforce Certified MuleSoft Developer II (MCD Level 2)'.
    
    Gere exatamente {qtd_lote} questões de múltipla escolha inéditas, de nível difícil e baseadas em cenários reais de produção.
    
    Seção alvo: {secao_info['nome']}
    Tópicos críticos para aprofundar: {secao_info['foco']}{evitar_txt}
    
    Instruções:
    1. Baseie todas as questões e explicações estritamente na documentação oficial da MuleSoft (docs.mulesoft.com) na versão 'latest'.
    2. No campo 'url_referencia', utilize SEMPRE o caminho '/latest/' (nunca use versões fixas como /4.4/, /2.3/ ou /2.x/), escolhendo preferencialmente uma destas páginas oficiais reais nas quais a questão foi baseada:
{lista_urls_txt}
    3. Use o estilo de cobrança e pegadinhas comuns de exames e simulados MCD Level 2 (como FreeCram e Marks4Sure) para calibrar a dificuldade.
    4. Evite questões puramente conceituais; crie cenários com trechos curtos de pom.xml, configurações de Maven, fluxos XML ou logs de erro.
    5. IMPORTANTE para formatação em tela pequena (e-reader): Mantenha eventuais trechos de código com linhas curtas (máximo 45 caracteres por linha) para evitar quebras ilegíveis.
    6. Escreva todo o conteúdo em Português, mas mantenha os termos técnicos da plataforma MuleSoft em Inglês (ex: Scatter-Gather, Object Store, Truststore, Parent POM, Autodiscovery).
    """

    usar_google_search = os.environ.get("USE_GOOGLE_SEARCH", "false").lower() == "true"
    ultimo_erro = None

    for idx, model_name in enumerate(modelos_candidatos):
        config_kwargs = {
            "response_mime_type": "application/json",
            "response_schema": BancoQuestoes,
            "temperature": 0.4,
        }
        if usar_google_search:
            config_kwargs["tools"] = [{"google_search": {}}]

        # No modelo principal (gemini-3.5-flash-lite, 500 req/dia), insiste até 5 vezes antes de cair para modelos de menor cota
        max_tentativas = 5 if idx == 0 else 2
        for tentativa in range(1, max_tentativas + 1):
            try:
                print(f"  -> Gerando lote de {qtd_lote} questão(ões) com '{model_name}' (tentativa {tentativa}/{max_tentativas})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs)
                )
                dados = json.loads(_limpar_json_texto(response.text))
                questoes = []
                for q in dados.get("questoes", []):
                    q["secao"] = secao_info["nome"]
                    q["url_referencia"] = normalizar_e_validar_url(q.get("url_referencia", ""), secao_info["nome"])
                    questoes.append(Questao(**q))
                return questoes
            except Exception as err:
                ultimo_erro = err
                err_str = str(err)
                if "503" in err_str or "UNAVAILABLE" in err_str or "500" in err_str or "overloaded" in err_str.lower():
                    espera = 5 * tentativa
                    print(f"  [Aviso] Alta demanda (503) em '{model_name}'. Aguardando {espera}s...")
                    time.sleep(espera)
                    continue
                elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    # Se for no modelo principal na 1ª tentativa, pode ser apenas limite por minuto (RPM); aguarda antes de desistir
                    if idx == 0 and tentativa < 3:
                        espera = 10 * tentativa
                        print(f"  [Aviso] Rate limit (429) em '{model_name}'. Aguardando {espera}s para manter prioridade no 3.5 Flash Lite...")
                        time.sleep(espera)
                        continue
                    print(f"  [Aviso] Cota/Rate limit (429) persistente em '{model_name}'. Alternando para próximo modelo...")
                    time.sleep(3)
                    break
                elif "404" in err_str or "NOT_FOUND" in err_str:
                    print(f"  [Aviso] Modelo '{model_name}' indisponível (404). Alternando para próximo...")
                    break
                else:
                    print(f"  [Aviso] Erro em '{model_name}': {err}. Tentando próximo modelo...")
                    break

    raise RuntimeError(f"Não foi possível gerar o lote após tentar todos os modelos. Último erro: {ultimo_erro}")


def buscar_e_gerar_questoes(
    client: genai.Client,
    secao_info: dict,
    modelos_candidatos: List[str],
    banco_completo: List[Questao],
    arquivo_backup: str = "MCD_Level_2_Reforco_backup.json",
    tamanho_lote: int = 4,
) -> None:
    meta = secao_info["qtd_questoes"]
    atuais = [q for q in banco_completo if q.secao == secao_info["nome"]]
    faltam = meta - len(atuais)

    if faltam <= 0:
        print(f"\n[OK] Seção '{secao_info['nome']}' já possui {len(atuais)}/{meta} questões no backup. Pulando...")
        return

    print(f"\nGerando {faltam} questão(ões) restante(s) para: {secao_info['nome']} (Nota: {secao_info['nota']})...")
    enunciados_existentes = [q.enunciado for q in atuais]

    while faltam > 0:
        qtd_lote = min(tamanho_lote, faltam)
        lote = _chamar_gemini_lote(
            client=client,
            secao_info=secao_info,
            qtd_lote=qtd_lote,
            modelos_candidatos=modelos_candidatos,
            enunciados_existentes=enunciados_existentes,
        )
        banco_completo.extend(lote)
        enunciados_existentes.extend(q.enunciado for q in lote)
        faltam -= len(lote)

        # Salva imediatamente no backup após cada lote
        with open(arquivo_backup, "w", encoding="utf-8") as f:
            json.dump([q.model_dump() for q in banco_completo], f, ensure_ascii=False, indent=2)
        print(f"  [Salvo] +{len(lote)} questões salvas (Total acumulado: {len(banco_completo)}/40).")

        if faltam > 0:
            time.sleep(2)


def criar_epub_xteink(todas_questoes: List[Questao], arquivo_saida: str = "MCD_Level_2_Reforco.epub"):
    book = epub.EpubBook()
    book.set_identifier("mcd-level-2-study-guide-2026")
    book.set_title("MCD Level 2 - Simulado Focado")
    book.set_language("pt-BR")
    book.add_author("MuleSoft Study Bot")

    # CSS minimalista otimizado para telas e-ink pequenas (Xteink X4)
    estilo_eink = """
    body {
        font-family: sans-serif;
        line-height: 1.4;
        margin: 5px;
        padding: 0;
    }
    h1, h2, h3 {
        font-size: 1.1em;
        border-bottom: 1px solid #000;
        padding-bottom: 3px;
    }
    pre {
        font-family: monospace;
        font-size: 0.75em;
        white-space: pre-wrap;
        word-wrap: break-word;
        background-color: #f4f4f4;
        padding: 6px;
        border: 1px solid #ccc;
    }
    .alternativa {
        margin-bottom: 8px;
    }
    .gabarito-box {
        page-break-before: always;
        border-top: 2px dashed #000;
        padding-top: 10px;
    }
    """
    css_item = epub.EpubItem(
        uid="style_eink",
        file_name="style/eink.css",
        media_type="text/css",
        content=estilo_eink.encode("utf-8")
    )
    book.add_item(css_item)

    capitulos = []

    # Agrupar questões por seção
    secoes_dict = {}
    for q in todas_questoes:
        secoes_dict.setdefault(q.secao, []).append(q)

    idx_cap = 1
    for secao, questoes in secoes_dict.items():
        cap = epub.EpubHtml(
            title=f"Seção {idx_cap}: {secao[:30]}...",
            file_name=f"sec_{idx_cap}.xhtml",
            lang="pt-BR"
        )
        cap.add_item(css_item)

        html_content = f"<h1>{html.escape(secao)}</h1>"

        for i, q in enumerate(questoes, 1):
            # Importante: html.escape evita que tags XML (<mule>, <dependency>) quebrem o XHTML do EPUB
            codigo_escapado = html.escape(q.codigo_xml_ou_dw.strip())
            codigo_html = f"<pre>{codigo_escapado}</pre>" if codigo_escapado else ""
            alts_html = "".join([f"<div class='alternativa'>{html.escape(alt)}</div>" for alt in q.alternativas])

            # Página da Questão
            html_content += f"""
            <div style="page-break-before: always;">
                <h3>Questão {idx_cap}.{i}</h3>
                <p>{html.escape(q.enunciado)}</p>
                {codigo_html}
                <div>{alts_html}</div>
            </div>
            """

            # Página seguinte com a Resposta (evita spoiler na tela pequena do X4)
            html_content += f"""
            <div class="gabarito-box">
                <h3>Gabarito {idx_cap}.{i}</h3>
                <p><strong>Correta:</strong> {html.escape(q.resposta_correta)}</p>
                <p><strong>Explicação:</strong> {html.escape(q.explicacao_oficial)}</p>
                <p><small>Ref: {html.escape(q.url_referencia)}</small></p>
            </div>
            """

        cap.content = html_content
        book.add_item(cap)
        capitulos.append(cap)
        idx_cap += 1

    book.toc = tuple(capitulos)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + capitulos

    epub.write_epub(arquivo_saida, book, {})
    print(f"\nArquivo EPUB gerado com sucesso: {arquivo_saida}")


if __name__ == "__main__":
    # Certifique-se de exportar sua chave: export GEMINI_API_KEY="sua-chave" (ou definir no .env)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Defina a variável de ambiente GEMINI_API_KEY antes de executar.")

    client = genai.Client(api_key=api_key)
    modelo_preferido = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    modelos_candidatos = obter_modelos_candidatos(client, modelo_preferido)
    print(f"[Info] Ordem de modelos configurada: {', '.join(modelos_candidatos[:5])}")

    arquivo_backup = "MCD_Level_2_Reforco_backup.json"
    banco_completo: List[Questao] = []

    # Carrega questões já geradas anteriormente para não perder progresso
    if os.path.exists(arquivo_backup):
        try:
            with open(arquivo_backup, "r", encoding="utf-8") as f:
                dados_antigos = json.load(f)
                for q in dados_antigos:
                    q["url_referencia"] = normalizar_e_validar_url(q.get("url_referencia", ""), q.get("secao", ""))
                    banco_completo.append(Questao(**q))
            print(f"[Info] {len(banco_completo)} questão(ões) carregada(s) e com referências 'latest' validadas.")
        except Exception as e:
            print(f"[Aviso] Não foi possível ler o backup anterior ({e}). Iniciando do zero.")

    for idx_sec, secao in enumerate(SECOES_PESOS):
        try:
            buscar_e_gerar_questoes(client, secao, modelos_candidatos, banco_completo, arquivo_backup)
            time.sleep(2)
        except Exception as e:
            print(f"Erro ao gerar seção {secao['nome']}: {e}")

    if banco_completo:
        # Ordena na ordem oficial das seções de SECOES_PESOS
        ordem_secoes = {s["nome"]: i for i, s in enumerate(SECOES_PESOS)}
        banco_completo.sort(key=lambda q: ordem_secoes.get(q.secao, 99))
        with open(arquivo_backup, "w", encoding="utf-8") as f:
            json.dump([q.model_dump() for q in banco_completo], f, ensure_ascii=False, indent=2)
        criar_epub_xteink(banco_completo)
