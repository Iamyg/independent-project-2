param(
    [string]$Docx = (Join-Path $PSScriptRoot '../report/Cquirrel_Q3_Reproduction_Report.docx'),
    [string]$Pdf = (Join-Path $PSScriptRoot '../report/Cquirrel_Q3_Reproduction_Report.pdf')
)
$ErrorActionPreference = 'Stop'
$taskDocx = [IO.Path]::GetFullPath($Docx)
$taskPdf = [IO.Path]::GetFullPath($Pdf)
$taskWord = $null
$taskDocument = $null
try {
    # Own a separate hidden Word instance; never attach to an existing document.
    $taskWord = New-Object -ComObject Word.Application
    $taskWord.Visible = $false
    $taskWord.DisplayAlerts = 0
    $taskWord.AutomationSecurity = 3
    $taskDocument = $taskWord.Documents.Open($taskDocx, $false, $true)
    $taskDocument.Repaginate()
    $taskDocument.ExportAsFixedFormat($taskPdf, 17)
    Write-Output "Exported $taskPdf"
    Write-Output "Pages: $($taskDocument.ComputeStatistics(2))"
}
finally {
    if ($null -ne $taskDocument) {
        $taskDocument.Close(0)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($taskDocument)
    }
    if ($null -ne $taskWord) {
        $taskWord.Quit()
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($taskWord)
    }
}
