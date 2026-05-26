{{/* vim: set filetype=mustache: */}}

{{/*
Base name for all resources. Defaults to the chart name (dclaw-<app>) so rendered
resource names match the live deployment exactly, independent of the release name.
*/}}
{{- define "dclaw.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Name of the app Secret consumed by the backend via envFrom. */}}
{{- define "dclaw.secretName" -}}
{{- default (printf "%s-secret" (include "dclaw.name" .)) .Values.secret.name }}
{{- end }}

{{/* dpanel app id (chart name without the dclaw- prefix), e.g. "monitor". */}}
{{- define "dclaw.appId" -}}
{{- default (.Chart.Name | trimPrefix "dclaw-") .Values.appId }}
{{- end }}
