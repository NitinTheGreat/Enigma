[CmdletBinding()]
param(
    [string]$Project = 'aeza-brand-analytics',
    [string]$Region = 'asia-southeast1',
    [string]$Repository = 'aeza',
    [string]$Service = 'enigma-demo'
)

$ErrorActionPreference = 'Stop'
$demo = $PSScriptRoot
$tag = (git -C $demo rev-parse --short HEAD).Trim()
$image = "$Region-docker.pkg.dev/$Project/$Repository/${Service}:$tag"

function Invoke-Gcloud {
    & gcloud @args
    if ($LASTEXITCODE -ne 0) { throw "gcloud $($args[0..1] -join ' ') failed with exit code $LASTEXITCODE" }
}

if ($Service -like 'aeza-*' -or $Service -like 'conjunction-*') {
    throw 'Refusing to overwrite another project''s service.'
}
if (-not (Test-Path (Join-Path $demo 'out/index.html'))) {
    throw 'No built bundle. Run npm run build first.'
}

Write-Host "Building $image"
Invoke-Gcloud builds submit $demo --project $Project --tag $image --quiet

Write-Host "Deploying $Service"
Invoke-Gcloud run deploy $Service --project $Project --region $Region --image $image `
    --allow-unauthenticated --port 8080 --memory 256Mi --cpu 1 --min-instances 0 --max-instances 2 --quiet

$url = (& gcloud run services describe $Service --project $Project --region $Region --format 'value(status.url)').Trim()
Write-Host ""
Write-Host "Enigma demo live at $url"
