"""VS Code adapter only; the library itself is completely VS Code-independent.

Started by VS Code with Python -I -S.  No sockets/network listeners.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

# -I removes the script directory from sys.path. Explicitly allow our own
# packaged source root, without enabling third-party site packages (-S).
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from zizai_slides import compile, convert_text, __version__


def main():
    try:
        request = json.load(sys.stdin)
        op = request.get('action','parse')
        if op == 'ping':
            print(json.dumps({'ok': True, 'version': __version__, 'python': sys.executable,
                              'engineRoot': str(Path(__file__).resolve().parents[1])}, ensure_ascii=False))
            return
        source = request.get('text')
        if not isinstance(source,str) or len(source)>2_000_000:
            raise ValueError('textは2MB以内の文字列にしてください。')
        if op == 'parse':
            result = {'ok':True,'deck':compile(source,style_path=request.get('stylePath'))}
        elif op == 'convert':
            dest = request.get('output','')
            mode = request.get('mode','editable')
            path = convert_text(source,dest,mode,request.get('sourceDir','.'),style_path=request.get('stylePath'))
            result = {'ok':True,'path':str(path),'mode':mode}
        else:
            raise ValueError('不明な操作です。')
    except (OSError,TypeError,ValueError,RuntimeError) as err:
        result = {'ok':False,'error':str(err)}
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
