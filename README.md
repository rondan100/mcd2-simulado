# 📚 Gerador de Simulado MCD Level 2 (EPUB p/ Xteink X4)

Script automatizado em Python que utiliza a API **Google Gemini (`gemini-3.5-flash-lite`)** com *Structured Outputs* (`Pydantic`) e *Google Search Grounding* para gerar um simulado focado nas seções de reforço do exame **Salesforce Certified MuleSoft Developer II (MCD Level 2)** e compilar um e-book `.epub` otimizado para telas e-ink compactas (como o **Xteink X4**).

## 🛠️ Instalação e Uso

```powershell
cd d:\Desenv\Workspaces\WSPOCs\mcd2-simulado
pip install -r requirements.txt

# Defina sua chave de API do Gemini no PowerShell (ou em um arquivo .env):
$env:GEMINI_API_KEY="sua_chave_aqui"

# Execute o gerador:
python gerar_simulado_mcd2.py
```

### Arquivos Gerados
- `MCD_Level_2_Reforco.epub`: E-book formatado com cada questão em uma página e o gabarito comentado na página seguinte (evitando *spoilers* em telas pequenas).
- `MCD_Level_2_Reforco_backup.json`: Backup estruturado com todas as 40 questões geradas.
