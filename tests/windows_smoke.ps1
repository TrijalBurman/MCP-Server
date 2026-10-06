$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Workspace = Split-Path -Parent $PSScriptRoot
$FakeFolder = Join-Path $Workspace '.runtime\ollama'
$FakeExe = Join-Path $FakeFolder 'ollama.exe'
$AppPort = 8791
$AppUrl = "http://127.0.0.1:$AppPort"
$AppProcess = $null

# This tiny fixture simulates Ollama's local HTTP listener. It performs no inference
# and makes no network requests, so CI never downloads models or needs a GPU.
$FakeSource = @'
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
public class FakeOllama {
    public static int Main(string[] args) {
        if (args.Length == 0) return 1;
        if (args[0] == "pull") return 0;
        if (args[0] != "serve") return 1;
        string host = Environment.GetEnvironmentVariable("OLLAMA_HOST");
        if (host != "127.0.0.1:11435") return 2;
        if (Environment.GetEnvironmentVariable("OLLAMA_NO_CLOUD") != "1") return 3;
        var listener = new TcpListener(IPAddress.Loopback, 11435);
        listener.Start();
        while (true) {
            using (var client = listener.AcceptTcpClient()) {
                using (var stream = client.GetStream()) {
                    stream.ReadTimeout = 5000;
                    var reader = new StreamReader(stream, Encoding.ASCII, false, 1024, true);
                    string line = reader.ReadLine() ?? "";
                    string path = line.Split(' ').Length > 1 ? line.Split(' ')[1] : "";
                    string header;
                    while (!String.IsNullOrEmpty(header = reader.ReadLine())) { }
                    string json = path == "/api/version" ? "{\"version\":\"ci-fixture\"}" : "{\"models\":[]}";
                    string status = path == "/api/version" || path == "/api/tags" ? "200 OK" : "404 Not Found";
                    byte[] body = Encoding.UTF8.GetBytes(json);
                    byte[] response = Encoding.ASCII.GetBytes("HTTP/1.1 " + status + "\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: " + body.Length + "\r\nConnection: close\r\n\r\n");
                    stream.Write(response, 0, response.Length);
                    stream.Write(body, 0, body.Length);
                }
            }
        }
    }
}
'@

function Wait-Ready {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($null -ne $AppProcess -and $AppProcess.HasExited) {
            throw 'Windows launcher exited before the app became ready.'
        }
        try { return Invoke-RestMethod "$AppUrl/api/status" -TimeoutSec 2 } catch { Start-Sleep -Seconds 1 }
    }
    throw 'The Windows app did not become ready.'
}

function Send-Json($Path, $Body) {
    $Bytes = [System.Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 10))
    return Invoke-RestMethod "$AppUrl/api/$Path" -Method Post -Body $Bytes -ContentType 'application/json; charset=utf-8' -TimeoutSec 30
}

try {
    New-Item -ItemType Directory -Force $FakeFolder | Out-Null
    if (Test-Path -LiteralPath $FakeExe) { throw 'Refusing to overwrite an existing Ollama executable in the smoke test.' }
    Add-Type -TypeDefinition $FakeSource -OutputAssembly $FakeExe -OutputType ConsoleApplication
    Push-Location $Workspace
    try {
        & .\scripts\setup-models.cmd
        if ($LASTEXITCODE -ne 0) { throw 'The Windows model setup launcher failed against the offline fixture.' }
        $Stdout = Join-Path $Workspace '.runtime\smoke-app.stdout.log'
        $Stderr = Join-Path $Workspace '.runtime\smoke-app.stderr.log'
        $AppProcess = Start-Process -FilePath $env:ComSpec -ArgumentList '/d /c scripts\start.cmd -Port 8791' -WorkingDirectory $Workspace -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -PassThru
        $Status = Wait-Ready
        if ($Status.edition -ne 'windows' -or -not $Status.local_only) { throw 'Wrong app edition or local-only status.' }
        $Folder = Join-Path $Workspace '.runtime\smoke knowledge'
        New-Item -ItemType Directory -Force $Folder | Out-Null
        [System.IO.File]::WriteAllText((Join-Path $Folder 'notes.md'), 'Nimbus uses a local SQLite database.', [System.Text.Encoding]::UTF8)
        $Root = Send-Json 'roots' @{path=$Folder; label='Native Windows smoke'}
        [void](Send-Json 'index' @{root_id=$Root.id})
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            $IndexStatus = Invoke-RestMethod "$AppUrl/api/status" -TimeoutSec 3
            if (-not $IndexStatus.indexing.running) { break }
            Start-Sleep -Seconds 1
        }
        $Documents = (Invoke-RestMethod "$AppUrl/api/documents" -TimeoutSec 3).documents
        if ($Documents.Count -ne 1) { throw 'The native launcher could not index a local document.' }
        $Chat = Send-Json 'chat' @{message='What does Nimbus use?'}
        if ($Chat.content -notmatch 'SQLite' -or $Chat.mode -ne 'extractive') { throw 'Native MCP fallback retrieval failed.' }
        $Remember = Send-Json 'chat' @{message='remember that keep everything local'}
        if ($Remember.content -notmatch 'Saved') { throw 'Persistent memory failed through the native launcher.' }
        & .\scripts\stop.cmd
        if ($LASTEXITCODE -ne 0) { throw 'The Windows stop launcher failed.' }
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            $Client = New-Object System.Net.Sockets.TcpClient
            try { $Client.Connect('127.0.0.1', 11435); $Open = $true } catch { $Open = $false } finally { $Client.Dispose() }
            if (-not $Open) { break }
            Start-Sleep -Seconds 1
        }
        if ($Open) { throw 'The owned Ollama child survived stopping the Windows launcher.' }
        Write-Host 'Native Windows setup/start/stop, local indexing, real MCP retrieval and persistent memory smoke passed.'
    } finally { Pop-Location }
} finally {
    if (Test-Path -LiteralPath (Join-Path $Workspace '.venv\Scripts\python.exe')) {
        & (Join-Path $Workspace '.venv\Scripts\python.exe') -m copilot.windows_runtime stop
    }
    if (Test-Path -LiteralPath $FakeExe) { Remove-Item -LiteralPath $FakeExe -Force }
}
