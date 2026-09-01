import numpy as np
import xarray as xr
from pathlib import Path
from collections import Counter
import os

DATA_DIR = Path(os.environ.get("IAVNS_DATA_DIR", "./DataSets"))

f = next((DATA_DIR / "NSIDC _AMSR2_Sea_Ice").glob("*.nc"))
ds = xr.open_dataset(f)
ice = ds.ICECON.isel(time=0).values.ravel()
print("n", ice.size)
print("==0", int((ice==0).sum()), "==1.016", int(np.isclose(ice, 1.016).sum()))
print("in (0,1]", int(((ice>0)&(ice<=1)).sum()))
print("in (0.01,0.99)", int(((ice>0.01)&(ice<0.99)).sum()))
hist, edges = np.histogram(ice, bins=[-0.01,0,0.1,0.3,0.5,0.7,0.9,1.0,1.02,2])
print(list(zip(edges, hist)))
print("scale_factor", ds.ICECON.encoding)
print(ds.ICECON.encoding)
ds.close()

# calibration xml peek
import xml.etree.ElementTree as ET
xmlp = next((DATA_DIR / "Sentinel-1_SAR.SAFE").rglob("calibration-*.xml"))
print("cal xml", xmlp)
tree = ET.parse(xmlp)
root = tree.getroot()
# strip ns
def local(t):
    return t.split("}")[-1] if "}" in t else t
tags = Counter(local(e.tag) for e in root.iter())
print("xml tags", tags.most_common(20))
for e in root.iter():
    if local(e.tag) == "calibrationVector":
        kids = [(local(c.tag), (c.text or "")[:80]) for c in e]
        print("first calibrationVector children", kids)
        break
