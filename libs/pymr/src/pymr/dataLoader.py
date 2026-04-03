from pathlib import Path
from cyvcf2 import VCF
import pandas as pd
from pandas import DataFrame

def loadGWAS(path: Path) -> DataFrame:
    vcf = VCF(path)
    records = []
    for variant in vcf:
        records.append({
            "CHROM": variant.CHROM,
            "POS":   variant.POS,
            "ID":    variant.ID,
            "REF":   variant.REF,
            "ALT":   str(variant.ALT[0]) if variant.ALT else ".",
            "QUAL":  variant.QUAL,
            "FILTER": variant.FILTER,
            "AF":    variant.INFO.get("AF"),
            "DP":    variant.INFO.get("DP", 0),
        })
    
    vcf.close()
    return pd.DataFrame(records)