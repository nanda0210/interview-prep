#!/usr/bin/env bash
# Fetch all child issues of a Jira epic into the schema understood by
# generate_interview_doc.py.
#
# Usage:
#   export JIRA_BASE_URL=https://cisco-cxe.atlassian.net
#   export JIRA_PAT=<your-personal-access-token>
#   bash fetch_tickets.sh FSRE-20 > artifacts/fsre-20/tickets.json
#
# Notes:
#   - Uses Bearer (PAT) auth — works with Jira Data Center / Cloud PAT.
#   - Pulls description as plain text via expand=renderedFields.
#   - Does NOT fetch PR linkage; produce prs.json separately (see SKILL.md).
set -euo pipefail

EPIC_KEY="${1:?usage: fetch_tickets.sh <EPIC_KEY>}"
: "${JIRA_BASE_URL:?JIRA_BASE_URL must be set}"
: "${JIRA_PAT:?JIRA_PAT must be set}"

JQL="\"Epic Link\" = ${EPIC_KEY} OR key = ${EPIC_KEY}"

curl -sS -H "Authorization: Bearer ${JIRA_PAT}" \
     -H "Accept: application/json" \
     -G "${JIRA_BASE_URL}/rest/api/3/search" \
     --data-urlencode "jql=${JQL}" \
     --data-urlencode "fields=summary,status,issuetype,priority,labels,components,fixVersions,assignee,reporter,description,created,resolutiondate,customfield_10016,comment,issuelinks" \
     --data-urlencode "maxResults=200" \
     --data-urlencode "expand=renderedFields" \
| jq --arg ek "${EPIC_KEY}" --arg base "${JIRA_BASE_URL}" '
{
  epic_key: $ek,
  generated_at: (now | todate),
  issues: [
    .issues[] | {
      key: .key,
      url: ($base + "/browse/" + .key),
      summary: .fields.summary,
      issuetype: .fields.issuetype.name,
      status: .fields.status.name,
      priority: (.fields.priority.name // null),
      labels: .fields.labels,
      components: [.fields.components[]?.name],
      fix_versions: [.fields.fixVersions[]?.name],
      assignee: (.fields.assignee.displayName // null),
      reporter: (.fields.reporter.displayName // null),
      story_points: .fields.customfield_10016,
      created: .fields.created,
      resolved: .fields.resolutiondate,
      description: (.fields.description | tostring),
      comments: [(.fields.comment.comments // [])[] | {author: .author.displayName, body: (.body | tostring), created: .created}],
      linked_issues: [(.fields.issuelinks // [])[] | {key: ((.outwardIssue // .inwardIssue).key), type: .type.name}],
      prs: []
    }
  ]
}'
