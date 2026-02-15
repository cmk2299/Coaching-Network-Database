# FORCE STREAMLIT REDEPLOY

**Issue**: Decision Makers still showing "No data available" after commit 936246a
**Root Cause**: Streamlit Cloud hasn't redeployed yet OR is using stale cache

## Verification

✅ Data IS on GitHub (commit 936246a):
```bash
$ git show 936246a:tmp/preloaded/alexander_blessin.json | wc -c
239734  # ✅ 239 KB (not stub data!)

$ git show 936246a:tmp/preloaded/alexander_blessin.json | jq '.decision_makers.total'
4  # ✅ Decision makers are there
```

❌ But Streamlit Cloud still shows old version

## Solution: Force Redeploy

### Option 1: Dummy commit (quickest)
```bash
echo "# Force redeploy $(date)" >> DEPLOYMENT_TRIGGER.txt
git add DEPLOYMENT_TRIGGER.txt
git commit -m "Force Streamlit redeploy - cache update"
git push
```

### Option 2: Manual reboot in Streamlit Cloud
1. Go to https://share.streamlit.io/
2. Find "coaching-network-database"
3. Click "⋮" menu → "Reboot app"
4. Wait 2-3 minutes
5. Hard refresh browser (Cmd+Shift+R)

### Option 3: Clear Streamlit cache in code
Add cache clearing to dashboard startup:
```python
# In dashboard/app.py at the top
import streamlit as st
st.cache_data.clear()
st.cache_resource.clear()
```

## Expected Timeline

- Commit push: ~10 seconds
- Streamlit detection: ~30 seconds
- Build time: ~2-3 minutes
- **Total**: ~3-4 minutes from push to live

## Verification Steps

After deployment:
1. **Hard refresh browser**: Cmd+Shift+R (not just F5!)
2. **Clear browser cache**: Cmd+Shift+Delete → Clear browsing data
3. **Incognito mode**: Open in new incognito window
4. Check Decision Makers tab for Blessin

Expected result:
- 🎯 Hiring Managers: 2
- Timeline: Johannes Spors (Genua CFC, 2022)
- Timeline: Andreas Bornemann (FC St. Pauli, 2024-present)
