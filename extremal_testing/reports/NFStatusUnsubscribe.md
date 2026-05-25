# NFStatusUnsubscribe Bug Report

- Source results: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/test_results/NFStatusUnsubscribe.json`
- Source tests: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/testcases/NFStatusUnsubscribe.json`
- Anomaly tests reviewed: 3
- Reports selected: 2

## 1. Inconsistent Handling of Invalid Subscription ID Patterns

Different implementations show inconsistent behavior when handling subscription IDs that do not match the required pattern. free5gc returns a 204 status code, indicating success, while oai and open5gs return a 404 status code, indicating not found.

- Possibly affected implementations: free5gc
- Evidence strength: 8/10
- Rationale: free5gc does not enforce the pattern constraint for subscription IDs.
- Why investigate: Ensuring consistent validation of subscription ID patterns across implementations is crucial for interoperability.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| path.subscriptionID | path.subscriptionID | true | {"pattern": "^([0-9]{5,6}-(x3Lf57A:nid=[A-Fa-f0-9]{11}:)?)?[^-]+$", "type": "string"} |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_2_neg: Invalid Subscription ID Pattern | path.subscriptionID MUST match the pattern ^([0-9]{5,6}-(x3Lf57A:nid=[A-Fa-f0-9]{11}:)?)?[^-]+$. | DELETE /subscriptions/12345-invalid-pattern | status=204 | status=404; body=<!DOCTYPE html><html lang="en"><title>404 Not Found</title><body><h1>404 Not Found</h1></body></html> | status=404; body={"type":"/nnrf-nfm/v1","title":"Not found","status":404,"detail":"12345-invalid-pattern","instance":"/subscriptions/12345-invalid-pattern"} |

## 2. Inconsistent Response for Missing Subscription ID

When the subscription ID is not provided, open5gs returns a 400 status code indicating a bad request, while free5gc and oai return a 404 status code indicating not found.

- Possibly affected implementations: open5gs
- Evidence strength: 7/10
- Rationale: open5gs returns a different status code compared to other implementations when the subscription ID is missing.
- Why investigate: Understanding the rationale for different status codes can improve error handling consistency.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| path.subscriptionID | path.subscriptionID | true | {"pattern": "^([0-9]{5,6}-(x3Lf57A:nid=[A-Fa-f0-9]{11}:)?)?[^-]+$", "type": "string"} |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_3_neg: Subscription ID Not Provided | path.subscriptionID MUST be provided. | DELETE /subscriptions/ | status=404; body=404 page not found | status=404; body=<!DOCTYPE html><html lang="en"><title>404 Not Found</title><body><h1>404 Not Found</h1></body></html> | status=400; body={"type":"/nnrf-nfm/v1","title":"No SubscriptionId","status":400,"instance":"/subscriptions"} |
