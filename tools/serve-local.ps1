param([int]$Port = 8000)
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
$listener.Start()
Write-Host "Local site: http://localhost:$Port/"
$types = @{'.html'='text/html; charset=utf-8';'.css'='text/css';'.js'='application/javascript';'.png'='image/png';'.jpg'='image/jpeg';'.svg'='image/svg+xml';'.mp4'='video/mp4';'.otf'='font/otf';'.woff2'='font/woff2';'.json'='application/json'}
try {
    while ($true) {
        $client = $listener.AcceptTcpClient()
        try {
            $stream = $client.GetStream()
            $reader = [IO.StreamReader]::new($stream)
            $request = $reader.ReadLine()
            if (!$request) { continue }
            while ($reader.ReadLine()) {}
            $parts = $request.Split(' ')
            $url = [Uri]::UnescapeDataString(($parts[1].Split('?')[0]))
            if ($url -eq '/') { $url = '/index.html' }
            $path = [IO.Path]::GetFullPath((Join-Path $root $url.TrimStart('/')))
            $status = '200 OK'
            $mime = $types[[IO.Path]::GetExtension($path).ToLowerInvariant()]
            if (!$mime) { $mime = 'application/octet-stream' }
            if (!$path.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or !(Test-Path -LiteralPath $path -PathType Leaf)) {
                $status = '404 Not Found'
                $bytes = [Text.Encoding]::UTF8.GetBytes('Not found')
            } else { $bytes = [IO.File]::ReadAllBytes($path) }
            $header = [Text.Encoding]::ASCII.GetBytes("HTTP/1.1 $status`r`nContent-Type: $mime`r`nContent-Length: $($bytes.Length)`r`nConnection: close`r`n`r`n")
            $stream.Write($header, 0, $header.Length)
            if ($parts[0] -ne 'HEAD') { $stream.Write($bytes, 0, $bytes.Length) }
        } catch { Write-Warning $_ } finally { $client.Dispose() }
    }
} finally { $listener.Stop() }
