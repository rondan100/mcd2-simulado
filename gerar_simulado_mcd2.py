"""
Gerador de Simulado Focado MCD Level 2 (MuleSoft Certified Developer II)
com padrão oficial da banca (SYSTEM_PROMPT_BANCA + subtópicos críticos)
e saída otimizada em EPUB para telas e-ink compactas (ex: Xteink X4).
"""

import argparse
import glob
import os
import re
import html
import json
import time
import urllib.request
from datetime import datetime
from typing import List, Optional
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
    secao: str = Field(description="Nome da seção oficial do exame MCD Level 2")
    enunciado: str = Field(description="Cenário prático de desenvolvimento, arquitetura ou troubleshooting no estilo da prova MuleSoft")
    codigo_xml_ou_dw: str = Field(default="", description="Bloco Exhibit com XML, pom.xml, Log4j2, Policy ou DataWeave realista (máx 45 chars/linha) ou vazio se não aplicável")
    alternativas: List[str] = Field(description="4 alternativas no formato 'A) ...', 'B) ...', 'C) ...', 'D) ...'")
    resposta_correta: str = Field(description="Letra e texto exato da alternativa correta")
    explicacao_oficial: str = Field(description="Explicação técnica detalhada baseada na doc oficial /latest/, justificando por que a correta está certa e por que cada um dos 3 distratores está errado")
    url_referencia: str = Field(description="URL oficial existente da documentação MuleSoft usando a versão /latest/")


class BancoQuestoes(BaseModel):
    questoes: List[Questao]


# 2. Prompt Mestre calibrado com o estilo real da banca oficial da MuleSoft (MCD - Level 2)
SYSTEM_PROMPT_BANCA = """
Você é um especialista certificador da MuleSoft responsável por criar questões oficiais para o exame
"Salesforce Certified MuleSoft Developer II (MCD - Level 2)".

REGRAS DE CRIAÇÃO (Baseadas na Documentação Oficial Mule 4 / Anypoint Platform na versão /latest/):
1. ESTILO CIRÚRGICO DO ENUNCIADO (IGUAL À PROVA REAL):
   - Nunca faça perguntas teóricas genéricas ("O que é X?").
   - Seja objetivo e direto (2 a 4 frases curtas), apresentando um cenário real de desenvolvimento,
     arquitetura, custo operacional ou troubleshooting (exatamente como nas questões oficiais do MCD Level 2).
   - Quando o tópico envolver XML, configuração de conectores/TLS, policies, Object Store, Log4j2, Maven ou DataWeave,
     preencha "codigo_xml_ou_dw" com um Exhibit compacto e realista (5 a 12 linhas, máx. 45 chars/linha).
2. NÍVEL DE PROFUNDIDADE E PEGADINHAS CLÁSSICAS DA BANCA:
   - Foque em comportamentos internos reais do runtime Mule 4:
     * Exceções específicas: OS:KEY_NOT_FOUND, MULE:RETRY_EXHAUSTED, MULE:COMPOSITE_ROUTING,
       MULE:DUPLICATE_MESSAGE, MULE:REDELIVERY_EXHAUSTED, HTTP:UNAUTHORIZED.
     * Expressões exatas: error.errorMessage.payload.failures['2'], #[correlationId], etc.
     * Timing e ordem de execução:
       - Object Store: uma chave expirada pelo entryTtl só é efetivamente removida quando a thread
         de expiração roda no expirationInterval (ex.: se entryTtl=1s, expirationInterval=30s e o
         retrieve ocorre após 10s, o valor armazenado ainda é retornado!).
       - Custom Policies com <http-policy:execute-next/>: Policy A (Order 1) e Policy B (Order 2)
         executam em pilha (A1 -> B1 -> F1 -> B2 -> A2).
       - HTTP Request com TLS Configuration = None em HTTPS usa o truststore padrão da JRE (cacerts).
       - HTTP Listener síncrono retorna o Correlation ID no response header por padrão (sem ação extra).
3. CONSTRUÇÃO DAS 4 ALTERNATIVAS (A, B, C, D):
   - Apenas 1 alternativa deve ser estritamente correta de acordo com a documentação oficial da MuleSoft.
   - As 4 alternativas devem ter tamanho e estrutura semelhantes (não torne a certa obviamente mais longa!).
   - Crie 3 distratores altamente plausíveis usando:
     a) Inversão de termos técnicos (ex: Keystore vs Truststore, Appenders vs Loggers, On Error Continue vs On Error Propagate).
     b) Configurações incompletas, parâmetros inexistentes ou ordem invertida (ex: B1, A1, F1, A2, B2).
     c) Anti-patterns que até funcionam em dev, mas falham em produção ou violam requisitos de custo/escala
        (ex: 10 agendamentos/localizações no API Functional Monitoring; gravar >10MB direto no Object Store v2).
4. EXPLICAÇÃO DA DOCUMENTAÇÃO ("explicacao_oficial"):
   - Explique com precisão técnica por que a alternativa correta está certa (citando tags, erros ou comportamentos da doc)
     E explique objetivamente por que cada uma das outras 3 alternativas está incorreta.
5. FORMATAÇÃO PARA E-READER (Xteink X4) E REFERÊNCIAS:
   - Linhas de código em "codigo_xml_ou_dw" com no máximo 45 caracteres por linha.
   - No campo "url_referencia", utilize SEMPRE URLs existentes de docs.mulesoft.com na versão "/latest/".

EXEMPLOS DE CALIBRAÇÃO DE ESTILO (NÃO copie literalmente; crie cenários inéditos com o mesmo rigor e concisão):
- Exemplo A (Exhibit XML + Timing interno):
  Enunciado: "Analise o Exhibit. Um Object Store está configurado com entryTtl de 2 segundos e expirationInterval de 60 segundos. Qual será o resultado se o processamento entre os:store e os:retrieve levar 15 segundos?"
  Exhibit:
    <os:object-store name="os"
      entryTtl="2" entryTtlUnit="SECONDS"
      expirationInterval="60"
      expirationIntervalUnit="SECONDS"/>
    <os:store objectStore="os" key="#['k1']">
      <os:value>#['storedVal']</os:value>
    </os:store>
    <os:retrieve objectStore="os" key="#['k1']">
      <os:default-value>#['defVal']</os:default-value>
    </os:retrieve>
  Alternativas concisas (A: origVal, B: OS:KEY_NOT_FOUND, C: storedVal, D: defVal) -> Correta: C (pois a thread de expiração só roda a cada 60s).

- Exemplo B (Exhibit Policy + Ordem de execução):
  Enunciado: "Analise o Exhibit. Uma aplicação Mule possui duas Custom Policies: Policy X (Order 1) e Policy Y (Order 2). Quando uma requisição HTTP chega ao endpoint, qual será a ordem exata de execução?"
  Exhibit:
    <http-policy:proxy name="policy-X">
      <http-policy:source>
        <X1/><http-policy:execute-next/><X2/>
      </http-policy:source>
    </http-policy:proxy>
    <http-policy:proxy name="policy-Y">
      <http-policy:source>
        <Y1/><http-policy:execute-next/><Y2/>
      </http-policy:source>
    </http-policy:proxy>
  Alternativas concisas (A: Y1,X1,F1,X2,Y2 | B: X1,Y1,F1,Y2,X2 | C: X1,X2,Y1,Y2,F1 | D: F1,X1,Y1,Y2,X2) -> Correta: B.

- Exemplo C (Exhibit Config + Truststore JRE):
  Enunciado: "Analise o Exhibit. O fluxo invoca uma API externa via HTTPS com TLS Configuration definido como None no HTTP Request. Se o certificado da API alvo for assinado por uma CA, o que é verdade?"
  Exhibit:
    Flow: HTTP:GET /items -> HTTPS:GET /list
    HTTP Request Config:
      Protocol: HTTPS
      TLS Configuration: None
  Alternativas concisas contrastando default truststore vs default keystore da JRE -> Correta: sucesso se o certificado da CA estiver no truststore padrão da JRE.
"""


# 3. Configuração de Pesos Baseada no Resultado + Subtópicos Críticos da Banca (MCD - Level 2)
# Quanto menor a nota, maior a quantidade de questões geradas
SECOES_PESOS = [
    {
        "nome": "Implement Maintainable and Modular Mule Applications and Their Maven Build",
        "nota": "47%",
        "qtd_questoes": 12,
        "foco": "Reutilização de módulos via Maven (classifier mule-plugin vs jar), Parent POM, BOM (Bill of Materials), MUnit coverage/failBuild, shared libraries vs domains, externalized properties, exchange deployment.",
        "subtopicos": [
            "Reutilização de módulos Mule publicados no Nexus/Exchange via Maven (classifier mule-plugin vs jar)",
            "Inclusão de bibliotecas Java legadas reutilizáveis: instalar em repositório Maven e referenciar no pom.xml",
            "Parent POM e BOM (Bill of Materials) com <type>pom</type> e <scope>import</scope> no dependencyManagement",
            "MUnit Maven Plugin: coverage-report, <failBuild>true</failBuild> e thresholds (Application, Resource, Flow)",
            "Deploy no CloudHub/RTF com Mule Maven Plugin referenciando credenciais no settings.xml (<server>)",
            "Shared Resources / Domain Projects (on-premises) vs Mule Libraries no CloudHub",
            "Hierarquia de precedência de propriedades externas (Deployment > System > Env > YAML > Global)",
            "Publicação de assets reutilizáveis no Anypoint Exchange via Maven Facade API v3",
            "Validação de JSON Schema via JSON Module (json:validate-schema) vs API Manager Policy",
            "Herança de versões de conectores em aplicações filhas usando Parent POM corporativo",
            "Execução de MUnit assertions e Mock When em pipelines CI/CD sem dependências externas",
            "Empacotamento de bibliotecas compartilhadas de Error Handler global como mule-plugin",
        ],
    },
    {
        "nome": "Implement Performant and Reliable Mule Applications",
        "nota": "50%",
        "qtd_questoes": 12,
        "foco": "Scatter-Gather error handling (error.errorMessage.payload.failures), Until Successful + Try Scope + On Error Continue para erros permanentes (401/400), Parallel For Each vs Scatter-Gather, Object Store v2 (entryTtl vs expirationInterval e limite >10MB no CloudHub 2.0), Idempotent Message Validator, Redelivery Policy, VM Queues, Streaming, Cache Scope.",
        "subtopicos": [
            "Scatter-Gather error handling: acesso à rota que falhou via error.errorMessage.payload.failures['N'] para compensação",
            "Until Successful combinado com Try Scope e On Error Continue para erros permanentes (HTTP:UNAUTHORIZED/400) reduzindo latência",
            "Padrão Saga com Scatter-Gather vs Parallel For Each para invocar múltiplas APIs HTTP em paralelo e fazer rollback sequencial",
            "Object Store: pegadinha de entryTtl vs expirationInterval (ex: entryTtl=1s, expirationInterval=30s e retrieve após 10s)",
            "Limitações do Object Store v2 para arquivos grandes (>10MB) no CloudHub 2.0: armazenamento externo + chave/localização no OSv2",
            "Padrão HTTP Webhook para uma Web API notificar clientes imediatamente sobre mudanças de estado",
            "Idempotent Message Validator (idExpression padrão e tratamento de MULE:DUPLICATE_MESSAGE)",
            "Redelivery Policy (<redelivery-policy maxRedeliveryCount>) em VM/JMS Listeners e MULE:REDELIVERY_EXHAUSTED",
            "VM Queues (TRANSIENT vs PERSISTENT) vs Anypoint MQ em arquiteturas multi-worker",
            "Streaming strategies: Repeatable File Store Stream (inMemorySize) e evitar materialização (orderBy/groupBy)",
            "Cache Scope (<ee:cache filterExpression>) e expiração baseada em tempo no Object Store",
            "Comportamento de payload e isolamento de variáveis em falhas parciais dentro de Parallel For Each",
        ],
    },
    {
        "nome": "Secure Data at Rest and In Transit",
        "nota": "67%",
        "qtd_questoes": 7,
        "foco": "mTLS (two-way TLS) no HTTP Listener (Keystore + Truststore), HTTP Request com TLS None (truststore padrão da JRE), OAuth 2.0 Authorization Code e Client Credentials no HTTP Connector, Secure Properties Tool (chaves e valores diferentes por ambiente), Safely Hiding Properties, Cryptography Module (JCE/PGP).",
        "subtopicos": [
            "Configuração de mTLS (two-way TLS) no HTTP Listener (Keystore + Truststore)",
            "HTTP Request com TLS None usando o truststore padrão da JRE (cacerts) vs TLS Context customizado",
            "Propriedades obrigatórias do OAuth 2.0 Authorization Code grant type no HTTP Connector",
            "Secure Properties Tool: chaves diferentes por ambiente e valores diferentes por ambiente (Blowfish/AES + CBC)",
            "HTTP Request com OAuth 2.0 Client Credentials e renovação automática via refreshTokenWhen em 401",
            "Safely Hiding Properties: mascaramento de chaves sensíveis via secureProperties no mule-artifact.json",
            "Cryptography Module: PGP Decrypt com validação de assinatura (publicKeyRingFileName) e JCE Asymmetric Sign",
        ],
    },
    {
        "nome": "Implement Monitorable Mule Applications",
        "nota": "67%",
        "qtd_questoes": 7,
        "foco": "Log4j2.xml (AsyncLogger para pacotes específicos dentro da tag Loggers), Tracing Module (With CorrelationID no Anypoint MQ), Endpoints de Readiness vs Liveness, API Functional Monitoring (otimização de custos e Secrets), Custom Business Events, Anypoint Monitoring Custom Metrics e Alerts.",
        "subtopicos": [
            "Log4j2.xml: adição de <AsyncLogger name='org.mule.extensions.vm' level='ERROR'/> dentro da tag <Loggers> (vs <Appenders>)",
            "Tracing Module: uso do escopo With CorrelationID envolvendo Anypoint MQ Publish para propagar Order ID como Correlation ID",
            "Retorno automático do mesmo Correlation ID no HTTP response header em APIs síncronas com HTTP Listener (comportamento padrão)",
            "Endpoints de Readiness vs Liveness: status da API e conectividade/reachability com sistemas subjacentes (ex: MySQL)",
            "API Functional Monitoring: otimização de custos e overhead operacional usando uma localização pública e um agendamento único",
            "API Functional Monitoring (BAT CLI): uso de Anypoint Secrets Manager para mascarar credenciais em monitores",
            "Anypoint Monitoring Custom Metrics (<custom-metrics:send>) vs Custom Business Events (<tracking:custom-event>) e Alertas",
        ],
    },
    {
        "nome": "Expose Production-Ready Anypoint Platform-Managed APIs From Mule Applications",
        "nota": "88%",
        "qtd_questoes": 2,
        "foco": "Ordem de execução de Custom Policies (http-policy:execute-next) com múltiplas políticas (Order 1, Order 2), API Autodiscovery, Gatekeeper, Automated Policies, validação de JSON Schema.",
        "subtopicos": [
            "Ordem de execução de Custom Policies (http-policy:execute-next) com múltiplas políticas (Order 1, Order 2)",
            "API Autodiscovery (anypoint.platform.client_id/client_secret), Gatekeeper e publicação de Custom Policies no Exchange",
        ],
    },
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
        "https://docs.mulesoft.com/json-module/latest/",
    ],
    "Implement Performant and Reliable Mule Applications": [
        "https://docs.mulesoft.com/mule-runtime/latest/scatter-gather-concept",
        "https://docs.mulesoft.com/mule-runtime/latest/until-successful-scope",
        "https://docs.mulesoft.com/mule-runtime/latest/try-scope-concept",
        "https://docs.mulesoft.com/mule-runtime/latest/parallel-foreach-scope",
        "https://docs.mulesoft.com/mule-runtime/latest/idempotent-message-validator",
        "https://docs.mulesoft.com/mule-runtime/latest/streaming-about",
        "https://docs.mulesoft.com/mule-runtime/latest/cache-scope",
        "https://docs.mulesoft.com/mule-runtime/latest/redelivery-policy",
        "https://docs.mulesoft.com/vm-connector/latest/",
        "https://docs.mulesoft.com/object-store/latest/osv2-guide",
        "https://docs.mulesoft.com/object-store/latest/osv2-faq",
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
        "https://docs.mulesoft.com/mule-runtime/latest/logging-in-mule",
        "https://docs.mulesoft.com/mule-runtime/latest/correlation-id",
        "https://docs.mulesoft.com/tracing-module/latest/",
        "https://docs.mulesoft.com/mule-runtime/latest/business-events",
        "https://docs.mulesoft.com/monitoring/latest/logs",
        "https://docs.mulesoft.com/monitoring/latest/anypoint-custom-metrics",
        "https://docs.mulesoft.com/monitoring/latest/alerts",
        "https://docs.mulesoft.com/runtime-fabric/latest/deploy-to-runtime-fabric",
        "https://docs.mulesoft.com/api-functional-monitoring/latest/",
        "https://docs.mulesoft.com/api-functional-monitoring/latest/bat-secret-create-task",
    ],
    "Expose Production-Ready Anypoint Platform-Managed APIs From Mule Applications": [
        "https://docs.mulesoft.com/api-manager/latest/api-autodiscovery",
        "https://docs.mulesoft.com/api-manager/latest/custom-policy",
        "https://docs.mulesoft.com/json-module/latest/",
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
    "api-functional-monitoring": "https://docs.mulesoft.com/api-functional-monitoring/latest/",
    "api-autodiscovery-concept-mule-4": "https://docs.mulesoft.com/api-manager/latest/api-autodiscovery",
    "custom-policies-configure": "https://docs.mulesoft.com/api-manager/latest/custom-policy",
    "osv2-guide": "https://docs.mulesoft.com/object-store/latest/osv2-guide",
    "osv2-faq": "https://docs.mulesoft.com/object-store/latest/osv2-faq",
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
        r"^https://docs\.mulesoft\.com/(exchange|monitoring|object-store|runtime-fabric|api-functional-monitoring|tracing-module|json-module)/(?!latest/)(.+)$",
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


def montar_prompt_lote(
    secao_info: dict,
    subtopicos_lote: List[str],
    enunciados_existentes: List[str],
    idioma: str = "pt",
) -> str:
    evitar_txt = ""
    if enunciados_existentes:
        resumo_existentes = "\n".join(f"- {e[:90]}..." for e in enunciados_existentes[-10:])
        evitar_txt = f"\nNão repita cenários já abordados nestas questões anteriores:\n{resumo_existentes}\n"

    urls_oficiais = URLS_DOCS_OFICIAIS_LATEST.get(secao_info["nome"], [])
    lista_urls_txt = "\n".join(f"  - {u}" for u in urls_oficiais)
    lista_subtopicos_txt = "\n".join(f"  {i + 1}. {st}" for i, st in enumerate(subtopicos_lote))

    regra_idioma = (
        "Escreva enunciado, alternativas e explicação em INGLÊS (idêntico ao idioma oficial do exame MCD Level 2)."
        if idioma == "en"
        else "Escreva em PORTUGUÊS, mantendo todos os termos técnicos da plataforma MuleSoft em Inglês (ex: Scatter-Gather, Object Store v2, Truststore, Keystore, AsyncLogger, Try Scope, On Error Continue)."
    )

    return f"""
Gere exatamente {len(subtopicos_lote)} questão(ões) inédita(s) no padrão exato da banca do exame MCD Level 2 — sendo 1 questão específica para cada subtópico numerado abaixo:

SEÇÃO OFICIAL: {secao_info['nome']}
SUBTÓPICOS DESTE LOTE:
{lista_subtopicos_txt}
{evitar_txt}
PÁGINAS OFICIAIS VERIFICADAS (/latest/) PARA EMBASAMENTO E 'url_referencia':
{lista_urls_txt}

Certifique-se de que:
- {regra_idioma}
- A terminologia (nomes de conectores, tags XML, expressões DataWeave e tipos de erro) esteja 100% fiel à documentação oficial Mule 4 (/latest/).
- As 4 alternativas tenham tamanho equilibrado e distratores cirúrgicos (sem deixar a correta obviamente mais longa).
- Cada questão traga um Exhibit compacto e realista em 'codigo_xml_ou_dw' (máx. 45 chars/linha) sempre que envolver XML, pom.xml, Log4j2, policy, configuração TLS ou DataWeave.
- Em 'explicacao_oficial', justifique claramente por que a alternativa correta está certa E por que cada uma das outras 3 alternativas está errada.
"""


def _chamar_gemini_lote(
    client: genai.Client,
    secao_info: dict,
    subtopicos_lote: List[str],
    modelos_candidatos: List[str],
    enunciados_existentes: List[str],
    idioma: str = "pt",
) -> List[Questao]:
    qtd_lote = len(subtopicos_lote)
    prompt = montar_prompt_lote(secao_info, subtopicos_lote, enunciados_existentes, idioma=idioma)

    usar_google_search = os.environ.get("USE_GOOGLE_SEARCH", "false").lower() == "true"
    ultimo_erro = None

    for idx, model_name in enumerate(modelos_candidatos):
        config_kwargs = {
            "system_instruction": SYSTEM_PROMPT_BANCA,
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
                    # Se for no modelo principal nas primeiras tentativas, pode ser limite por minuto (RPM); aguarda antes de desistir
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
    arquivo_backup: str,
    historico_enunciados: Optional[List[str]] = None,
    tamanho_lote: int = 3,
    idioma: str = "pt",
) -> None:
    meta = secao_info["qtd_questoes"]
    atuais = [q for q in banco_completo if q.secao == secao_info["nome"]]
    ja_geradas = len(atuais)
    faltam = meta - ja_geradas

    if faltam <= 0:
        print(f"\n[OK] Seção '{secao_info['nome']}' já possui {ja_geradas}/{meta} questões no backup. Pulando...")
        return

    print(f"\nGerando {faltam} questão(ões) restante(s) para: {secao_info['nome']} (Nota: {secao_info['nota']})...")
    enunciados_existentes = list(historico_enunciados or []) + [q.enunciado for q in atuais]
    subtopicos = secao_info.get("subtopicos", [secao_info["foco"]])
    cursor_subtopico = ja_geradas

    while faltam > 0:
        qtd_lote = min(tamanho_lote, faltam)
        subtopicos_lote = [
            subtopicos[(cursor_subtopico + i) % len(subtopicos)]
            for i in range(qtd_lote)
        ]
        lote = _chamar_gemini_lote(
            client=client,
            secao_info=secao_info,
            subtopicos_lote=subtopicos_lote,
            modelos_candidatos=modelos_candidatos,
            enunciados_existentes=enunciados_existentes,
            idioma=idioma,
        )
        banco_completo.extend(lote)
        enunciados_existentes.extend(q.enunciado for q in lote)
        cursor_subtopico += len(lote)
        faltam -= len(lote)

        # Salva imediatamente no backup após cada lote
        with open(arquivo_backup, "w", encoding="utf-8") as f:
            json.dump([q.model_dump() for q in banco_completo], f, ensure_ascii=False, indent=2)
        print(f"  [Salvo] +{len(lote)} questões salvas em '{arquivo_backup}' (Total acumulado: {len(banco_completo)}/40).")

        if faltam > 0:
            time.sleep(2)


def obter_proxima_edicao(diretorio: str = ".") -> int:
    """Detecta o número da próxima edição com base nos EPUBs já existentes na pasta."""
    epubs = glob.glob(os.path.join(diretorio, "MCD_Level_2_Reforco*.epub"))
    maior = 0
    for caminho in epubs:
        nome = os.path.basename(caminho)
        match = re.search(r"_Ed(\d+)_", nome)
        if match:
            maior = max(maior, int(match.group(1)))
        else:
            maior = max(maior, 1)
    return maior + 1


def carregar_historico_enunciados(diretorio: str = ".", ignorar_arquivo: Optional[str] = None) -> dict:
    """Lê backups anteriores para evitar repetir cenários em novas edições."""
    historico = {}
    backups = sorted(glob.glob(os.path.join(diretorio, "MCD_Level_2_Reforco*backup.json")))
    for caminho in backups:
        if ignorar_arquivo and os.path.abspath(caminho) == os.path.abspath(ignorar_arquivo):
            continue
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
                for q in dados:
                    secao = q.get("secao", "")
                    enunciado = q.get("enunciado", "")
                    if secao and enunciado:
                        historico.setdefault(secao, []).append(enunciado)
        except Exception:
            pass
    return historico


def _obter_capa_svg_fallback(edicao: int, data_legivel: str, total_questoes: int) -> bytes:
    """Fallback em SVG puro de alto contraste (e-ink) caso capa_mcd2.png não exista."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800" width="600" height="800">
  <rect width="600" height="800" fill="#ffffff"/>
  <rect x="24" y="24" width="552" height="752" fill="none" stroke="#000000" stroke-width="6"/>
  <rect x="38" y="38" width="524" height="724" fill="none" stroke="#000000" stroke-width="2"/>
  <text x="300" y="120" text-anchor="middle" font-family="sans-serif" font-size="22" font-weight="bold" fill="#000000">SALESFORCE • MULESOFT</text>
  <text x="300" y="235" text-anchor="middle" font-family="sans-serif" font-size="68" font-weight="bold" fill="#000000">MCD LEVEL 2</text>
  <rect x="70" y="275" width="460" height="58" fill="#000000"/>
  <text x="300" y="313" text-anchor="middle" font-family="sans-serif" font-size="26" font-weight="bold" fill="#ffffff">SIMULADO FOCADO • MULE 4</text>
  <circle cx="300" cy="480" r="88" fill="none" stroke="#000000" stroke-width="5"/>
  <circle cx="170" cy="480" r="24" fill="#000000"/>
  <circle cx="430" cy="480" r="24" fill="#000000"/>
  <line x1="194" y1="480" x2="212" y2="480" stroke="#000000" stroke-width="5"/>
  <line x1="388" y1="480" x2="406" y2="480" stroke="#000000" stroke-width="5"/>
  <text x="300" y="492" text-anchor="middle" font-family="monospace" font-size="36" font-weight="bold" fill="#000000">API</text>
  <text x="300" y="655" text-anchor="middle" font-family="sans-serif" font-size="28" font-weight="bold" fill="#000000">EDIÇÃO #{edicao:02d}</text>
  <text x="300" y="698" text-anchor="middle" font-family="sans-serif" font-size="20" fill="#333333">{total_questoes} QUESTÕES • DOCS LATEST</text>
  <text x="300" y="732" text-anchor="middle" font-family="sans-serif" font-size="18" fill="#555555">{data_legivel}</text>
</svg>"""
    return svg.encode("utf-8")


def criar_epub_xteink(
    todas_questoes: List[Questao],
    arquivo_saida: str,
    edicao: int = 1,
    timestamp: Optional[str] = None,
    caminho_capa: str = "capa_mcd2.jpg",
    idioma: str = "pt",
):
    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_legivel = datetime.now().strftime("%d/%m/%Y %H:%M")

    book = epub.EpubBook()
    # Identificador e título únicos por edição para que o e-reader liste cada simulado separadamente
    book.set_identifier(f"mcd-level-2-simulado-ed{edicao:02d}-{timestamp}")
    book.set_title(f"MCD Level 2 - Simulado #{edicao:02d}")
    book.set_language("en" if idioma == "en" else "pt-BR")
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
    .cover-page {
        text-align: center;
        margin: 0;
        padding: 4px;
    }
    .cover-img {
        max-width: 100%;
        max-height: 82vh;
        height: auto;
        border: 1px solid #000;
    }
    .cover-meta {
        margin-top: 8px;
        font-size: 0.85em;
        font-weight: bold;
        border-top: 1px solid #000;
        padding-top: 5px;
    }
    .exhibit-label {
        font-size: 0.85em;
        font-weight: bold;
        margin-top: 6px;
        margin-bottom: 2px;
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

    # Configuração da Capa (thumbnail da biblioteca + primeira página do e-book)
    pasta_script = os.path.dirname(os.path.abspath(__file__))
    candidatos_capa = [
        (os.path.join(pasta_script, caminho_capa), "images/cover.jpg" if caminho_capa.lower().endswith((".jpg", ".jpeg")) else "images/cover.png"),
        (os.path.join(pasta_script, "capa_mcd2.jpg"), "images/cover.jpg"),
        (os.path.join(pasta_script, "capa_mcd2.png"), "images/cover.png"),
    ]
    capa_encontrada = None
    for caminho_abs, nome_interno in candidatos_capa:
        if os.path.exists(caminho_abs):
            capa_encontrada = (caminho_abs, nome_interno)
            break

    if capa_encontrada:
        caminho_abs, capa_arquivo_interno = capa_encontrada
        with open(caminho_abs, "rb") as f_capa:
            capa_bytes = f_capa.read()
        book.set_cover(capa_arquivo_interno, capa_bytes, create_page=False)
    else:
        capa_arquivo_interno = "images/cover.svg"
        capa_bytes = _obter_capa_svg_fallback(edicao, data_legivel, len(todas_questoes))
        book.set_cover(capa_arquivo_interno, capa_bytes, create_page=False)

    pagina_capa = epub.EpubHtml(
        title=f"Capa - Edição #{edicao:02d}",
        file_name="cover.xhtml",
        lang="en" if idioma == "en" else "pt-BR",
    )
    pagina_capa.add_item(css_item)
    pagina_capa.content = f"""
    <div class="cover-page">
        <img class="cover-img" src="{capa_arquivo_interno}" alt="Capa MCD Level 2 - Edição #{edicao:02d}" />
        <div class="cover-meta">
            EDIÇÃO #{edicao:02d} • {len(todas_questoes)} QUESTÕES • {data_legivel}
        </div>
    </div>
    """
    book.add_item(pagina_capa)

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
            lang="en" if idioma == "en" else "pt-BR"
        )
        cap.add_item(css_item)

        html_content = f"<h1>{html.escape(secao)}</h1>"

        for i, q in enumerate(questoes, 1):
            # Importante: html.escape evita que tags XML (<mule>, <dependency>) quebrem o XHTML do EPUB
            codigo_limpo = q.codigo_xml_ou_dw.strip()
            if codigo_limpo and codigo_limpo.upper() != "N/A":
                codigo_html = f"<div class='exhibit-label'>Exhibit:</div><pre>{html.escape(codigo_limpo)}</pre>"
            else:
                codigo_html = ""
            alts_html = "".join([f"<div class='alternativa'>{html.escape(alt)}</div>" for alt in q.alternativas])
            explicacao_html = html.escape(q.explicacao_oficial).replace("\n", "<br/>")

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
                <p><strong>Explicação Oficial:</strong><br/>{explicacao_html}</p>
                <p><small>Ref: {html.escape(q.url_referencia)}</small></p>
            </div>
            """

        cap.content = html_content
        book.add_item(cap)
        capitulos.append(cap)
        idx_cap += 1

    book.toc = tuple([pagina_capa] + capitulos)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [pagina_capa, "nav"] + capitulos

    epub.write_epub(arquivo_saida, book, {})
    print(f"\nArquivo EPUB gerado com sucesso: {arquivo_saida} (Edição #{edicao:02d} com capa)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gerador de Simulado Focado MCD Level 2 (EPUB p/ Xteink X4)")
    parser.add_argument(
        "--retomar",
        metavar="ARQUIVO_JSON",
        help="Retoma uma geração interrompida a partir de um arquivo JSON de backup específico.",
    )
    parser.add_argument(
        "--somente-epub",
        nargs="?",
        const="__LATEST__",
        metavar="ARQUIVO_JSON",
        help="Gera um novo EPUB com capa a partir de um backup JSON existente (ou do mais recente) sem chamar a API.",
    )
    parser.add_argument(
        "--idioma",
        choices=["pt", "en"],
        default=os.environ.get("IDIOMA_SIMULADO", "pt"),
        help="Idioma das questões: 'pt' (Português com termos MuleSoft em Inglês) ou 'en' (Inglês igual à prova oficial).",
    )
    args = parser.parse_args()

    edicao_num = obter_proxima_edicao(".")
    timestamp_atual = datetime.now().strftime("%Y%m%d_%H%M%S")
    sufixo_idioma = "_EN" if args.idioma == "en" else ""
    arquivo_epub_saida = f"MCD_Level_2_Reforco_Ed{edicao_num:02d}{sufixo_idioma}_{timestamp_atual}.epub"

    banco_completo: List[Questao] = []

    if args.somente_epub:
        if args.somente_epub == "__LATEST__":
            backups_disp = sorted(glob.glob("MCD_Level_2_Reforco*backup.json"), key=os.path.getmtime, reverse=True)
            if not backups_disp:
                raise FileNotFoundError("Nenhum arquivo de backup JSON encontrado para gerar o EPUB.")
            arquivo_backup = backups_disp[0]
        else:
            arquivo_backup = args.somente_epub

        with open(arquivo_backup, "r", encoding="utf-8") as f:
            dados_antigos = json.load(f)
            for q in dados_antigos:
                q["url_referencia"] = normalizar_e_validar_url(q.get("url_referencia", ""), q.get("secao", ""))
                banco_completo.append(Questao(**q))
        print(f"[Info] {len(banco_completo)} questão(ões) carregada(s) de '{arquivo_backup}'.")
    else:
        if args.retomar:
            arquivo_backup = args.retomar
            if os.path.exists(arquivo_backup):
                with open(arquivo_backup, "r", encoding="utf-8") as f:
                    dados_antigos = json.load(f)
                    for q in dados_antigos:
                        q["url_referencia"] = normalizar_e_validar_url(q.get("url_referencia", ""), q.get("secao", ""))
                        banco_completo.append(Questao(**q))
                print(f"[Info] Retomando '{arquivo_backup}' com {len(banco_completo)} questão(ões) já salvas.")
        else:
            # Cada execução cria seu próprio arquivo de backup e seu próprio EPUB inédito
            arquivo_backup = f"MCD_Level_2_Reforco_Ed{edicao_num:02d}{sufixo_idioma}_{timestamp_atual}_backup.json"
            print(f"[Info] Iniciando nova edição #{edicao_num:02d} -> saída: '{arquivo_epub_saida}'")

        historico_por_secao = carregar_historico_enunciados(".", ignorar_arquivo=arquivo_backup)
        total_hist = sum(len(v) for v in historico_por_secao.values())
        if total_hist > 0:
            print(f"[Info] {total_hist} enunciado(s) de edições anteriores carregados para evitar repetições.")

        # Certifique-se de exportar sua chave: export GEMINI_API_KEY="sua-chave" (ou definir no .env)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Defina a variável de ambiente GEMINI_API_KEY antes de executar.")

        client = genai.Client(api_key=api_key)
        modelo_preferido = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
        modelos_candidatos = obter_modelos_candidatos(client, modelo_preferido)
        print(f"[Info] Ordem de modelos configurada: {', '.join(modelos_candidatos[:5])}")

        for secao in SECOES_PESOS:
            try:
                buscar_e_gerar_questoes(
                    client,
                    secao,
                    modelos_candidatos,
                    banco_completo,
                    arquivo_backup,
                    historico_enunciados=historico_por_secao.get(secao["nome"], []),
                    idioma=args.idioma,
                )
                time.sleep(2)
            except Exception as e:
                print(f"Erro ao gerar seção {secao['nome']}: {e}")

    if banco_completo:
        # Ordena na ordem oficial das seções de SECOES_PESOS
        ordem_secoes = {s["nome"]: i for i, s in enumerate(SECOES_PESOS)}
        banco_completo.sort(key=lambda q: ordem_secoes.get(q.secao, 99))
        with open(arquivo_backup, "w", encoding="utf-8") as f:
            json.dump([q.model_dump() for q in banco_completo], f, ensure_ascii=False, indent=2)
        criar_epub_xteink(
            banco_completo,
            arquivo_saida=arquivo_epub_saida,
            edicao=edicao_num,
            timestamp=timestamp_atual,
            idioma=args.idioma,
        )
