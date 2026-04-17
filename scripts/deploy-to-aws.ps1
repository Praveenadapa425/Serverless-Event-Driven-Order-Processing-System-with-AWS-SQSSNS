# AWS Setup and Deployment Script (PowerShell)
# Automates AWS deployment for Windows.

param(
    [string]$Stage = "dev",
    [string]$Region = "us-east-1",
    [string]$DbPassword = ""
)

$ProjectName = "serverless-order-processing"
$ErrorActionPreference = "Stop"
$env:SLS_DISABLE_ENTERPRISE = "1"
$env:SLS_TELEMETRY_DISABLED = "1"
$env:SLS_INTERACTIVE_SETUP_DISABLE = "1"

# In newer PowerShell versions, keep native stderr warnings from becoming terminating errors.
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Write-Header {
    param([string]$Message)
    Write-Host "`n====================================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "====================================================" -ForegroundColor Cyan
}

function Check-Command {
    param([string]$Command)
    $exists = $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
    if ($exists) {
        Write-Host "[OK] $Command found" -ForegroundColor Green
    }
    else {
        Write-Host "[ERROR] $Command is not installed" -ForegroundColor Red
    }
    return $exists
}

function Resolve-PythonCommand {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return "python"
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return "py"
    }
    return $null
}

function Invoke-Serverless {
    param([string[]]$CliArgs)
    if ($script:UseGlobalServerless) {
        serverless @CliArgs
    }
    else {
        npx -y serverless@3.38.0 @CliArgs
    }
}

function Invoke-PipInstall {
    param([string[]]$Args)
    if ($PythonCommand -eq "py") {
        $null = (& py -m pip --disable-pip-version-check @Args 2>&1)
    }
    else {
        $null = (& python -m pip --disable-pip-version-check @Args 2>&1)
    }
}

Write-Header "AWS Deployment Setup for Order Processing"

# Step 1: Check prerequisites
Write-Host "`n[1/9] Checking prerequisites..." -ForegroundColor Yellow

$commands = @("aws", "node", "npm")
$allFound = $true

foreach ($cmd in $commands) {
    if (-not (Check-Command $cmd)) {
        $allFound = $false
    }
}

if (-not $allFound) {
    Write-Host "Install the missing command(s) and re-run." -ForegroundColor Red
    exit 1
}

$PythonCommand = Resolve-PythonCommand
if (-not $PythonCommand) {
    Write-Host "[ERROR] Python is not installed (checked 'python' and 'py')." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python command resolved as '$PythonCommand'" -ForegroundColor Green

# Step 2: Configure AWS credentials folder
Write-Host "`n[2/9] Configuring AWS credentials..." -ForegroundColor Yellow

$awsFolder = Join-Path $env:USERPROFILE ".aws"
if (-not (Test-Path $awsFolder)) {
    New-Item -ItemType Directory -Path $awsFolder | Out-Null
    Write-Host "[OK] Created AWS folder" -ForegroundColor Green
}

$credentialsFile = Join-Path $awsFolder "credentials"
if (-not (Test-Path $credentialsFile)) {
    Write-Host "[ERROR] AWS credentials file not found at $credentialsFile" -ForegroundColor Red
    Write-Host "Run 'aws configure' first, then re-run this script." -ForegroundColor Yellow
    exit 1
}
else {
    Write-Host "[OK] AWS credentials file exists" -ForegroundColor Green
}

$configFile = Join-Path $awsFolder "config"
if (-not (Test-Path $configFile)) {
    $config = @"
[default]
region = $Region
output = json
"@
    Set-Content -Path $configFile -Value $config -Encoding ASCII
    Write-Host "[OK] AWS config created" -ForegroundColor Green
}
else {
    Write-Host "[OK] AWS config file exists" -ForegroundColor Green
}

# Step 3: Verify AWS credentials
Write-Host "`n[3/9] Verifying AWS credentials..." -ForegroundColor Yellow

try {
    $AccountId = aws sts get-caller-identity --query Account --output text
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to verify AWS credentials."
    }
    Write-Host "[OK] AWS credentials verified" -ForegroundColor Green
    Write-Host "     Account ID: $AccountId" -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] Failed to verify AWS credentials" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

# Step 4: Verify Serverless Framework (v3)
Write-Host "`n[4/9] Verifying Serverless Framework (v3)..." -ForegroundColor Yellow
$script:UseGlobalServerless = $false
npx -y serverless@3.38.0 --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Serverless v3 via npx unavailable on this Node runtime, falling back to global serverless" -ForegroundColor Yellow
    serverless --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to run Serverless CLI" -ForegroundColor Red
        exit 1
    }
    $script:UseGlobalServerless = $true
}
$serverlessVersion = Invoke-Serverless -CliArgs @("--version")
Write-Host "[OK] Serverless Framework ready" -ForegroundColor Green
Write-Host "     Version: $serverlessVersion" -ForegroundColor Green

# Step 5: Install Python dependencies
Write-Host "`n[5/9] Installing Python dependencies..." -ForegroundColor Yellow
Invoke-PipInstall @("install", "-q", "-r", "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Invoke-PipInstall @("install", "-r", "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to install Python dependencies" -ForegroundColor Red
        exit 1
    }
}
Write-Host "[OK] Dependencies installed" -ForegroundColor Green

# Step 6: Install Serverless plugins
Write-Host "`n[6/9] Installing Serverless plugins..." -ForegroundColor Yellow
$infrastructurePath = "infrastructure"
if (Test-Path $infrastructurePath) {
    Push-Location $infrastructurePath
    try {
        if (Test-Path "package.json") {
            npm install --loglevel=error --legacy-peer-deps | Out-Null
            if ($LASTEXITCODE -ne 0) {
                npm install --loglevel=error --legacy-peer-deps
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to install infrastructure npm dependencies."
                }
            }
            Write-Host "[OK] Serverless plugins installed" -ForegroundColor Green
        }
        else {
            Write-Host "[WARN] infrastructure/package.json not found; skipping plugin install" -ForegroundColor Yellow
        }
    }
    finally {
        Pop-Location
    }
}

# Step 7: Get database password
Write-Host "`n[7/9] Database configuration..." -ForegroundColor Yellow
if ([string]::IsNullOrWhiteSpace($DbPassword)) {
    $securePassword = Read-Host "Enter database password (minimum 8 characters)" -AsSecureString
    $ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    try {
        $DbPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

if ([string]::IsNullOrWhiteSpace($DbPassword) -or $DbPassword.Length -lt 8) {
    Write-Host "[ERROR] Password must be at least 8 characters" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Database password accepted" -ForegroundColor Green

# Step 8: Deploy to AWS
Write-Host "`n[8/9] Deploying to AWS..." -ForegroundColor Yellow
Write-Host "Starting deployment to '$Stage' in '$Region'..." -ForegroundColor Yellow

try {
    if (Test-Path "infrastructure/src") {
        Remove-Item -Recurse -Force "infrastructure/src"
    }
    Copy-Item -Recurse -Force "src" "infrastructure/src"

    $env:DB_PASSWORD = $DbPassword
    Push-Location infrastructure
    Invoke-Serverless -CliArgs @("deploy", "--stage", $Stage, "--region", $Region, "--param=dbPassword=$DbPassword", "--verbose")
    if ($LASTEXITCODE -ne 0) {
        throw "Serverless deployment failed."
    }
    Pop-Location
    Write-Host "[OK] Deployment completed successfully" -ForegroundColor Green
}
catch {
    if ((Get-Location).Path -like "*infrastructure") {
        Pop-Location
    }
    Write-Host "[ERROR] Deployment failed" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

# Step 9: Display deployment information
Write-Host "`n[9/9] Deployment information..." -ForegroundColor Yellow
Write-Host "`nService details:" -ForegroundColor Green
Push-Location infrastructure
Invoke-Serverless -CliArgs @("info", "--stage", $Stage, "--region", $Region)
Pop-Location

Write-Host "`nCloudFormation outputs:" -ForegroundColor Green
aws cloudformation describe-stacks --stack-name "$ProjectName-$Stage" --region $Region --query "Stacks[0].Outputs" --output table 2>$null

Write-Header "AWS Deployment Complete"
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Initialize DB: psql -h <RDS-ENDPOINT> -U postgres -d orders_db -f scripts/init-db.sql" -ForegroundColor White
Write-Host "2. Test API: use POST <API-ENDPOINT>/orders with JSON body" -ForegroundColor White
Write-Host "3. Monitor logs: serverless logs -f orderCreator --stage $Stage --region $Region --tail" -ForegroundColor White
Write-Host "4. Cleanup: serverless remove --stage $Stage --region $Region" -ForegroundColor White
