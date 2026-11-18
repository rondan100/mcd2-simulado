# 📚 Gerador de Simulado MCD Level 2 (EPUB p/ Xteink X4)

Script automatizado em Python que utiliza a API **Google Gemini (`gemini-3.5-flash-lite`)** com *Structured Outputs* (`Pydantic`), `SYSTEM_PROMPT_BANCA` no estilo oficial da prova (com *Exhibits*, distratores realistas e justificativa por alternativa) e validação automática de URLs `/latest/` da documentação MuleSoft para gerar um simulado focado do exame **Salesforce Certified MuleSoft Developer II (MCD Level 2)** e compilar um e-book `.epub` otimizado para telas e-ink compactas (como o **Xteink X4**).

## 🛠️ Instalação e Uso

```powershell
cd d:\Desenv\Workspaces\WSPOCs\mcd2-simulado
pip install -r requirements.txt

# Copie .env.example para .env e preencha sua GEMINI_API_KEY (ou defina no PowerShell):
$env:GEMINI_API_KEY="sua_chave_aqui"

# Gera automaticamente uma NOVA edição inédita (novo EPUB com capa + novo JSON, sem sobrescrever anteriores):
python gerar_simulado_mcd2.py

# Gera uma nova edição em Inglês (idêntico ao idioma da prova oficial):
python gerar_simulado_mcd2.py --idioma en

# Retoma uma geração interrompida a partir de um JSON de backup:
python gerar_simulado_mcd2.py --retomar MCD_Level_2_Reforco_Ed02_20261118_141500_backup.json

# Gera um novo EPUB com capa a partir do JSON mais recente sem chamar a API:
python gerar_simulado_mcd2.py --somente-epub
```

### Arquivos Gerados
- `MCD_Level_2_Reforco_EdXX_YYYYMMDD_HHMMSS.epub`: E-book único por edição com capa otimizada para e-ink ([capa_mcd2.jpg](capa_mcd2.jpg)), identificador/título exclusivos por edição e gabarito comentado na página seguinte (evitando *spoilers* em telas pequenas).
- `MCD_Level_2_Reforco_EdXX_YYYYMMDD_HHMMSS_backup.json`: Backup estruturado das 40 questões daquela edição (também lido nas próximas execuções para evitar repetição de cenários).
