# NFStatusUnsubscribe Bug Report

- Source results: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/test_results/NFStatusUnsubscribe.json`
- Source tests: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/testcases/NFStatusUnsubscribe.json`
- Anomaly tests reviewed: 3
- Reports selected: 1

## 1. Open5GS SubscriptionID Pattern and Presence Requirement

Open5GS exhibits unique behavior by enforcing both a valid subscriptionID pattern and its presence, returning specific errors when these conditions are not met.

- Possibly affected implementations: open5gs
- Evidence strength: 9/10
- Rationale: Open5GS consistently returns specific errors for invalid or missing subscriptionID, unlike other implementations.
- Implementation differences: Open5GS returns 404 with detail "12345-invalid-pattern" for invalid pattern and 400 with message "No SubscriptionId" when missing, while others return 204 or 404.
- Why investigate: Investigating Open5GS's strict subscriptionID requirements could uncover potential bugs or misconfigurations.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| path.subscriptionID | path.subscriptionID | true | {"pattern": "^([0-9]{5,6}-(x3Lf57A:nid=[A-Fa-f0-9]{11}:)?)?[^-]+$", "type": "string"} |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_1_neg: Invalid Subscription ID as Non-String | path.subscriptionID MUST be a string. | DELETE /subscriptions/12345 | status=204 | status=404; body=<!DOCTYPE html><html lang="en"><title>404 Not Found</title><body><h1>404 Not Found</h1></body></html> | status=404; body={"type":"/nnrf-nfm/v1","title":"Not found","status":404,"detail":"12345","instance":"/subscriptions/12345"} |
| tc_2_neg: Invalid Subscription ID Pattern | path.subscriptionID MUST match the pattern ^([0-9]{5,6}-(x3Lf57A:nid=[A-Fa-f0-9]{11}:)?)?[^-]+$. | DELETE /subscriptions/12345-invalid-pattern | status=204 | status=404; body=<!DOCTYPE html><html lang="en"><title>404 Not Found</title><body><h1>404 Not Found</h1></body></html> | status=404; body={"type":"/nnrf-nfm/v1","title":"Not found","status":404,"detail":"12345-invalid-pattern","instance":"/subscriptions/12345-invalid-pattern"} |
| tc_3_neg: Subscription ID Not Provided | path.subscriptionID MUST be provided. | DELETE /subscriptions/ | status=404; body=404 page not found | status=404; body=<!DOCTYPE html><html lang="en"><title>404 Not Found</title><body><h1>404 Not Found</h1></body></html> | status=400; body={"type":"/nnrf-nfm/v1","title":"No SubscriptionId","status":400,"instance":"/subscriptions"} |
