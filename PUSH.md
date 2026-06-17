# Push to GitHub (Thirukumaran-Senthilkumaran)

Run these in PowerShell from the project folder:

```powershell
Set-Location "c:\Users\thiru\OneDrive\Desktop\PQC-Migration-Gateway Based"

# Point remote at your account (fix if wrong)
git remote remove origin 2>$null
git remote add origin https://github.com/Thirukumaran-Senthilkumaran/pqc-migration-gateway.git

git add .
git commit -m "Rebuild: cloud PQC gateway with LAN connector and Streamlit UI"
git branch -M main
git push -u origin main
```

If the repo does not exist yet, create it first at:
https://github.com/new?name=pqc-migration-gateway
(owner: **Thirukumaran-Senthilkumaran**, empty — no README)

Then run `git push -u origin main` again.
