# Changelog

{{ range .Versions }}
## {{ .Tag.Name }} {{ if eq .Tag.Name (index $.Versions 0).Tag.Name }}Latest{{ end }}

{{ range .CommitGroups }}
### {{ .Title }}

{{ range .Commits }}
- **{{ .Subject }}**
{{ if .Body }}
  {{ .Body | trimPrefix "\n" | printf "%s" }}
{{ end }}
{{ end }}
{{ end }}

{{ if not .CommitGroups }}
### 🔍 Changes
{{ range .Commits }}
- **{{ .Subject }}**
{{ if .Body }}
  {{ .Body | trimPrefix "\n" | printf "%s" }}
{{ end }}
{{ end }}
{{ end }}
{{ end }}
