"""python -m zizai_slides deck.md deck.pptx --mode editable"""
import argparse
from . import convert

def main():
    parser = argparse.ArgumentParser(description='Zizai Slides Markdown → PowerPoint / HTML / PDF (Python standard library)')
    parser.add_argument('input', help='Input Markdown file')
    parser.add_argument('output', help='Output pptx/html/pdf file')
    parser.add_argument('--mode',choices=['editable','image','html','pdf'],default='editable')
    parser.add_argument('--style', help='スライドデザイン用CSS（--zs-* で上書き）')
    args = parser.parse_args()
    try:
        target = convert(args.input,args.output,args.mode,style_path=args.style)
        print(target)
    except (ValueError,OSError,RuntimeError) as exc:
        parser.exit(1,f'ERROR: {exc}\n')

if __name__=='__main__':
    main()
