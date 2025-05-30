# PowerShell script for Windows

# Az összes forrás fájlok listája
$sources = @(
    "pysagax/message/command.proto",
    "pysagax/message/data.proto",
    "pysagax/message/heading.proto",
    "pysagax/message/flight_info.proto",
    "pysagax/message/altiss_intra_uav.proto"
)

# Projekt gyökérkönyvtárának meghatározása (többszörös Split-Path használatával)
$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$projectRoot = Split-Path -Path (Split-Path -Path $scriptDir -Parent) -Parent

# Debug mód bekapcsolása
$VerbosePreference = "Continue"

# `protoc` elérési útja (ha nincs a PATH-ban)
# Ha a `protoc.exe` helye ismerős, add meg itt a teljes elérési útját, pl.:
# $protocPath = "C:\path\to\protoc.exe"
$protocPath = "protoc"  # csak akkor működik, ha a PATH-ban van

# Fordítási ciklus
foreach ($i in $sources) {
    Write-Output "Compiling $i"

    Write-Output "  Running protoc"
    & $protocPath --python_out=$projectRoot --mypy_out=$projectRoot --proto_path=$projectRoot "$projectRoot\$i"

    # Ha szükséges lenne a protoletariat használata, itt lehet aktiválni:
    # Write-Output "  Running protoletariat"
    # & protol --create-package --in-place --python-out=$projectRoot protoc --proto-path=$projectRoot "$i"
}