# Timestamp Plugin Changelog

This changelog tracks updates to the Obsidian Timestamp Utility plugin, which allows users to insert timestamps and rename files with timestamp prefixes in Obsidian.

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
