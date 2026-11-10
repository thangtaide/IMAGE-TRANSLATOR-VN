"""Print selected observed model diagnostics without changing evaluation outputs."""
import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[1]
paths=sorted((root/'output/translation-quality').glob('*/results.json'))
data=json.loads(paths[-1].read_text(encoding='utf-8'))
print(json.dumps({'source':str(paths[-1]),'technical_checks':data['technical_checks'],
                  'seconds_total':data['seconds_total'],'memory_after':data['memory_after'],
                  'problem_sentence':data['records'][1]},ensure_ascii=False,indent=2))
