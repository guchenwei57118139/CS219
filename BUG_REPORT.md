# BUG REPORT

Generated from `extremal_testing/data/test_results/*.json` and `extremal_testing/data/confidence_scores/*.json`.

Entries are grouped by operation. Duplicate testcase titles are merged only when they represent the same underlying issue.

## NFDeregister

### Missing nfInstanceID Path Parameter
- Testcase: `NFDeregister_tests.json#0` (`Missing nfInstanceID Path Parameter`)
- Violated constraint: `The path parameter 'nfInstanceID' is required.`
- Returns: `free5gc: 404; oai: timeout/no status; open5gs: 400`
- Confidence: `3/10`
- Why: Implementations differ but do not clearly violate the spec. DELETE to /nf-instances (missing required {nfInstanceId}) is an unknown endpoint so a 404 (free5gc) is reasonable. open5gs returns 400 'cannot parse HTTP message' which is also plausible if the server rejects the malformed/unsupported path. oai timed out (environment/availability issue). No definite RFC violation identified; differences likely due to routing/parsing behavior or test environment.

### Missing OAuth2 Authorization
- Testcase: `NFDeregister_tests.json#3` (`Missing OAuth2 Authorization`)
- Violated constraint: `The caller must be authorized using the oAuth2ClientCredentials security scheme with the scope 'nnrf-nfm:nf-instance:write'.`
- Returns: `free5gc: 204; oai: 204; open5gs: 400`
- Confidence: `9/10`
- Why: free5gc and oai returned 204 No Content despite the request lacking the required OAuth2 client credentials/scope — this allows deregistration without authorization and is likely a standards/security violation. open5gs returns 400 (parse error). It is possible an instance was configured without auth for testing, but absent that, the 204 responses are non‑compliant.

## NFListRetrieval

### Invalid limit zero
- Testcase: `NFListRetrieval_tests.json#2` (`Invalid limit zero`)
- Violated constraint: `The query parameter 'limit' is optional and, if present, must be an integer with a minimum value of 1.`
- Returns: `free5gc: 400; oai: 200; open5gs: 400`
- Confidence: `9/10`
- Why: The 'limit=0' parameter violates the minimum=1 rule. free5gc and open5gs return 400 which is appropriate (open5gs message is generic but status is correct). oai returns 200 with an empty list and therefore erroneously accepts an invalid limit — likely an RFC violation.

### Invalid page-size zero
- Testcase: `NFListRetrieval_tests.json#4` (`Invalid page-size zero`)
- Violated constraint: `The query parameter 'page-size' is optional and, if present, must be an integer with a minimum value of 1.`
- Returns: `free5gc: 400; oai: 200; open5gs: 400`
- Confidence: `9/10`
- Why: The 'page-size=0' parameter violates the minimum=1 rule. free5gc and open5gs respond with 400 (acceptable though free5gc message is odd and open5gs is generic). oai returns 200 and accepts the invalid value, which is likely non‑compliant with the spec.

### Missing OAuth2 Scope
- Testcase: `NFListRetrieval_tests.json#6` (`Missing OAuth2 Scope`)
- Violated constraint: `Access requires OAuth2 client credentials with scope 'nnrf-nfm:nf-instances:read'. This request omits that required scope.`
- Returns: `free5gc: 400; oai: 200; open5gs: 400`
- Confidence: `9/10`
- Why: Request lacks the required OAuth2 scope. The server should reject access (401/403). oai returns 200 (allowing access), and free5gc/open5gs return 400 — none return the expected 401/403. This behavior is likely a spec violation (could also be a configuration issue), but non‑compliant overall.

## NFProfileRetrieval

### Invalid requester-features as JSON
- Testcase: `NFProfileRetrieval_tests.json#2` (`Invalid requester-features as JSON object`)
- Violated constraint: `The query parameter 'requester-features' must conform to the SupportedFeatures schema (a string). Providing a JSON object violates this schema.`
- Returns: `free5gc: 200; oai: 200; open5gs: 400`
- Confidence: `7/10`
- Why: The query parameter 'requester-features' is supposed to be a string per the schema. Open5gs returning 400 (cannot parse HTTP message) is a plausible response if the client sent unencoded braces or the server enforces syntactic checks. free5gc and oai returning 200 and supplying the NF profile indicates they are lenient and not validating the query parameter type/format. This is likely a spec deviation (lack of input validation), though a 400 from the server can also result from an unencoded URL; behavior may depend on how the client encoded the value.

### Invalid OAuth2 Scope
- Testcase: `NFProfileRetrieval_tests.json#4` (`Invalid OAuth2 Scope`)
- Violated constraint: `Request must use OAuth2 client credentials with scope 'nnrf-nfm' or 'nnrf-nfm:nf-instances:read'. Using a token without these scopes violates the operation's security requirements.`
- Returns: `free5gc: 200; oai: 200; open5gs: 400`
- Confidence: `9/10`
- Why: The request used a token without the required 'nnrf-nfm' scopes. Returning a successful 200 is inconsistent with the security requirements; the server should reject the request (401/403) for missing/insufficient scope. free5gc and oai returning 200 therefore likely violate the RFC. Open5gs returning 400 is also not the correct OAuth error but at least does not accept the request; overall this indicates incorrect handling of OAuth scopes.

## NFRegister

### NFProfile missing addressing fields
- Testcase: `NFRegister_tests.json#3` (`NFProfile missing addressing fields`)
- Violated constraint: `An NFProfile must include at least one of the following: 'fqdn', 'ipv4Addresses', or 'ipv6Addresses'.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The RFC requires an NFProfile to include at least one of fqdn, ipv4Addresses or ipv6Addresses. Open5GS rejects the request (400) which matches the spec. free5gc and OAI accept (201); OAI even shows an empty ipv4Addresses array which does not satisfy the "at least one" requirement. Unless those implementations are explicitly auto-populating endpoints (not in the request), accepting this input is a protocol violation.

### Empty plmnList
- Testcase: `NFRegister_tests.json#6` (`Invalid empty plmnList`)
- Violated constraint: `If present, 'plmnList' MUST be an array with at least 1 item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: plmnList if present MUST contain at least one item. Open5GS returns 400 which follows the constraint. free5gc and OAI accept the empty array (201). Treating an explicit empty array as valid violates the requirement (unless the server treats the empty array as if the field were absent, which would be non-standard).

### Empty ipv6Addresses
- Testcase: `NFRegister_tests.json#12` (`Invalid empty ipv6Addresses`)
- Violated constraint: `If present, 'ipv6Addresses' MUST be an array with at least 1 item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: ipv6Addresses, when present, must be a non-empty array. Open5GS rejects the empty array (400) which is correct. free5gc and OAI accept (201) despite the empty list; that behavior is inconsistent with the constraint and likely non-compliant unless they internally ignore/override the empty field.

### Empty allowedNfTypes
- Testcase: `NFRegister_tests.json#15` (`Invalid allowedNfTypes empty array`)
- Violated constraint: `If present, 'allowedNfTypes' MUST be an array with at least 1 item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: allowedNfTypes must be an array with at least one item if present. Open5GS returns 400 which aligns with the spec. free5gc and OAI accept the empty array (201). Accepting an explicit empty allowedNfTypes is inconsistent with the constraint and likely a spec violation (unless interpreted as omitted by implementation).

### DefaultNotificationSubscriptions item missing callbackUri
- Testcase: `NFRegister_tests.json#25` (`DefaultNotificationSubscriptions item missing callbackUri`)
- Violated constraint: `defaultNotificationSubscriptions items MUST include both 'notificationType' and 'callbackUri'.`
- Returns: `free5gc: 201; oai: 400; open5gs: 400`
- Confidence: `9/10`
- Why: defaultNotificationSubscriptions items MUST include both notificationType and callbackUri. Open5GS and OAI reject (400). free5gc accepts and returns an entry with callbackUri set to an empty string — effectively auto-filling a missing required field. Accepting the request or injecting an empty callbackUri is non-compliant with the requirement to provide the field.

### Empty Vendor Features
- Testcase: `NFRegister_tests.json#31` (`supportedVendorSpecificFeatures with empty array value`)
- Violated constraint: `If present, 'supportedVendorSpecificFeatures' MUST be an object with at least 1 property and each property value MUST be an array with at least 1 item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: The payload provides supportedVendorSpecificFeatures.{"123456"} = [] which violates the schema (array must have >=1 item). open5gs rejects (400) while free5gc and oai accept (201). free5gc/oai are likely lax and non‑compliant with the RFC/schema (should reject).

### Missing required NFService fields
- Testcase: `NFRegister_tests.json#32` (`Missing required NFService fields`)
- Violated constraint: `In the NFService object, the properties 'serviceInstanceId', 'serviceName', 'versions', 'scheme' and 'nfServiceStatus' are required.`
- Returns: `free5gc: 201; oai: 400; open5gs: 400`
- Confidence: `9/10`
- Why: The NFService is missing required properties (versions, scheme, nfServiceStatus). oai and open5gs rejected (400) but free5gc accepted and returned 201 (filling empty/NULL fields). Accepting an incomplete NFService is a likely RFC/schema violation by free5gc.

### NFService with empty ipEndPoints
- Testcase: `NFRegister_tests.json#34` (`NFService with empty ipEndPoints`)
- Violated constraint: `In an NFService, if 'ipEndPoints' is present it MUST be an array with at least 1 item.`
- Returns: `free5gc: 400; oai: 201; open5gs: 201`
- Confidence: `7/10`
- Why: This test also uses versions as string values (e.g. "v1") which appears to cause free5gc's 400 (type unmarshal error) rather than the ipEndPoints issue. Spec requires ipEndPoints, if present, to have >=1 item; oai and open5gs accepted the payload (201) despite empty ipEndPoints. Those acceptances are likely non‑compliant; free5gc's rejection is justified but due to a different schema error (versions type).

### Port Out Of Range
- Testcase: `NFRegister_tests.json#36` (`IpEndPoint port out of range (too large)`)
- Violated constraint: `IpEndPoint 'port', when present, MUST be an integer between 0 and 65535 (inclusive).`
- Returns: `free5gc: 400; oai: 201; open5gs: 201`
- Confidence: `9/10`
- Why: Port=70000 is out of allowed range (0–65535). free5gc rejected the request but due to a versions type unmarshalling error, not the port. oai and open5gs accepted (201) despite the invalid port. Accepting an out‑of‑range port is a clear RFC/schema violation for those implementations.

### InterfaceUpfInfoItem Missing Endpoint Fields
- Testcase: `NFRegister_tests.json#37` (`InterfaceUpfInfoItem Missing Endpoint Fields`)
- Violated constraint: `InterfaceUpfInfoItem requires 'interfaceType' and MUST include at least one of 'endpointFqdn', 'ipv4EndpointAddresses' or 'ipv6EndpointAddresses'. This test omits all endpoint fields.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: InterfaceUpfInfoItem contains interfaceType but no endpointFqdn/ipv4EndpointAddresses/ipv6EndpointAddresses; spec requires at least one endpoint. open5gs rejects (400) while free5gc and oai accept (201). free5gc/oai acceptance likely violates the RFC/schema (should reject).

### PortRange Out Of Range
- Testcase: `NFRegister_tests.json#38` (`PortRange End Out Of Range`)
- Violated constraint: `PortRange objects, when present, MUST include 'start' and 'end', and both MUST be integers between 0 and 65535 (inclusive).`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: The request contained a PortRange with end=70000 (>65535). open5gs returned 400 (rejecting invalid input), while free5gc and oai returned 201 (accepted). free5gc's response also omitted the portRange and oai did not expose it, suggesting they silently ignored or dropped the invalid field. Per the schema constraint (start/end MUST be 0..65535), accepting or silently accepting malformed PortRange is non‑compliant. open5gs' rejection is the correct behavior.

### Invalid ipv4Addresses value
- Testcase: `NFRegister_tests.json#41` (`Invalid ipv4Addresses value`)
- Violated constraint: `Where a property references an external schema (e.g. Ipv4Addr), the value MUST conform to that referenced schema. This test provides an invalid IPv4 address that does not conform to Ipv4Addr.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: The request included an invalid IPv4 address '999.999.999.999'. open5gs returned 400 (rejecting), free5gc returned 201 and echoed the invalid address (violates IPv4 format validation), and oai returned 201 but replaced/normalized the address to '0.0.0.0' (silently altering/ignoring input). The server should validate and reject or explicitly report malformed address; echoing an invalid IPv4 is non‑compliant. open5gs' behavior is preferable.

## NFStatusNotify

### Notification Body Is Array
- Testcase: `NFStatusNotify_tests.json#0` (`Notification Body Is Array Instead of Object`)
- Violated constraint: `The request body must be a JSON object conforming to the NotificationData schema ($ref: '#/components/schemas/NotificationData').`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `8/10`
- Why: Spec requires a JSON object conforming to NotificationData; an array body is a malformed request and should result in 4xx (typically 400). open5gs returning 400 is appropriate. free5gc and oai returning 404 likely indicate the endpoint is not routed or a generic server page rather than proper validation — this is probably a non‑compliant behavior or a configuration issue.

### Invalid Content-Type for NFStatusNotify
- Testcase: `NFStatusNotify_tests.json#1` (`Invalid Content-Type for NFStatusNotify`)
- Violated constraint: `The request body content type must be 'application/json'.`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `7/10`
- Why: Content-Type must be application/json; a non-JSON content type should be rejected (415 or 400). open5gs returning 400 is reasonable. free5gc and oai returning 404 suggests misrouting or missing handler instead of proper content-type validation — likely a bug or configuration problem.

### Missing event and nfInstanceUri
- Testcase: `NFStatusNotify_tests.json#2` (`Missing event and nfInstanceUri in NotificationData`)
- Violated constraint: `The NotificationData object requires the 'event' and 'nfInstanceUri' properties.`
- Returns: `free5gc: 404; oai: 301; open5gs: 400`
- Confidence: `7/10`
- Why: Missing required properties ('event' and 'nfInstanceUri') makes the NotificationData invalid and should produce 400. open5gs returns 400 which matches expected validation. free5gc returning 404 and oai returning 301 (redirect) indicate wrong endpoint handling or server config rather than correct schema validation.

### Invalid Event Value
- Testcase: `NFStatusNotify_tests.json#3` (`Invalid event value in notification`)
- Violated constraint: `The 'event' property must be one of the NotificationEventType values: NF_REGISTERED, NF_DEREGISTERED, NF_PROFILE_CHANGED, or SHARED_DATA_CHANGED.`
- Returns: `free5gc: 404; oai: 301; open5gs: 400`
- Confidence: `7/10`
- Why: An unknown 'event' enum should be treated as an invalid request (400). open5gs returning 400 is correct. free5gc (404) and oai (301) again look like routing/endpoint issues or improper handling instead of proper request validation.

### NF_PROFILE_CHANGED without profile details
- Testcase: `NFStatusNotify_tests.json#4` (`NF_PROFILE_CHANGED without profile details`)
- Violated constraint: `If event is 'NF_PROFILE_CHANGED', at least one of 'nfProfile', 'profileChanges', or 'completeNfProfile' must be present.`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `8/10`
- Why: For NF_PROFILE_CHANGED the absence of profile details makes the payload invalid and should be rejected with 4xx (400). open5gs returning 400 is compliant. free5gc and oai returning 404 indicate the request hit a non-handling page or wrong path rather than performing proper validation — likely an implementation/configuration issue.

### Missing Required Profile
- Testcase: `NFStatusNotify_tests.json#5` (`NF_REGISTERED without nfProfile or completeNfProfile`)
- Violated constraint: `If 'event' is 'NF_REGISTERED', then at least one of 'nfProfile' or 'completeNfProfile' must be present in the NotificationData object.`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `8/10`
- Why: open5gs returns 400 with a parse/validation error which is appropriate for a malformed NF_STATUS notification (missing required nfProfile/completeNfProfile). free5gc and oai both returned 404 HTML pages, indicating the endpoint was not found (or the server/router is misconfigured). If the tested NRF endpoint is expected to exist, returning 404 is incorrect — the server should validate the request and return 400 for invalid NotificationData. The 404 responses may also indicate the implementation is not exposing this operation at that URI (configuration difference) rather than correct protocol behavior.

### Missing Shared Data
- Testcase: `NFStatusNotify_tests.json#6` (`Missing sharedDataChanges when event is SHARED_DATA_CHANGED`)
- Violated constraint: `If 'event' is 'SHARED_DATA_CHANGED', then 'sharedDataChanges' must be present in the NotificationData object.`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `8/10`
- Why: open5gs correctly rejects the request with 400 (missing sharedDataChanges when event=SHARED_DATA_CHANGED). free5gc and oai returned 404, suggesting the endpoint is not present or URL mismatch; that is not the expected behavior for an existing NRF instance (should return 400 for invalid body). Could be a configuration/endpoint difference rather than a validation implementation issue.

### Empty profileChanges array
- Testcase: `NFStatusNotify_tests.json#7` (`Empty profileChanges array`)
- Violated constraint: `When present, 'profileChanges' must be an array with at least one item and each item must conform to ChangeItem ($ref: 'TS29571_CommonData.yaml#/components/schemas/ChangeItem').`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `8/10`
- Why: open5gs returning 400 for an empty profileChanges array is consistent with input validation (array must have at least one item). free5gc and oai returned 404 (endpoint not found), which implies either the service/URI is missing or misconfigured. If the endpoint should exist, 404 is a violation (should return 400); otherwise this is an implementation/configuration difference.

### Invalid empty sharedDataChanges
- Testcase: `NFStatusNotify_tests.json#8` (`Invalid empty sharedDataChanges`)
- Violated constraint: `When present, 'sharedDataChanges' must be an array with at least one item and each item must conform to ChangeItem ($ref: 'TS29571_CommonData.yaml#/components/schemas/ChangeItem').`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `8/10`
- Why: open5gs returned 400 (cannot parse HTTP message) which is appropriate for an invalid empty sharedDataChanges array. free5gc and oai returned 404 HTML responses, indicating the endpoint was not reachable; that behavior is unexpected for a present NRF and likely indicates a configuration or deployment difference rather than correct protocol validation.

### Invalid nfProfile structure
- Testcase: `NFStatusNotify_tests.json#9` (`Invalid nfProfile structure`)
- Violated constraint: `If 'nfProfile' is present, it must conform to NFProfile ($ref: '#/components/schemas/NFProfile').`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `8/10`
- Why: open5gs rejected the request with 400 due to invalid nfProfile structure (e.g., wrong type for fqdn), which matches expected schema validation. free5gc and oai returned 404, implying the URI/operation was not exposed or reachable. If the endpoint exists, 404 is incorrect and constitutes non-conformance; otherwise this points to a missing endpoint/configuration mismatch.

### Notification with forbidden allowedPlmns
- Testcase: `NFStatusNotify_tests.json#10` (`Notification with forbidden allowedPlmns in nfProfile`)
- Violated constraint: `nfProfile and its NFService entries must not include allowedPlmns, allowedSnpns, allowedNfTypes, allowedNfDomains, or allowedNssais`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `8/10`
- Why: The request includes a forbidden nfProfile field (allowedPlmns). The correct behavior is to reject the request with a 4xx (typically 400 Bad Request) indicating invalid payload. open5gs returns 400 which is appropriate. free5gc and oai return 404 Not Found HTML pages — that indicates either the callback endpoint is not implemented/configured or they are returning an incorrect status for a malformed body. If the endpoint exists, returning 404 is not compliant with expected validation behavior. Likely an implementation/configuration issue for free5gc and oai.

### Invalid Content-Encoding Type
- Testcase: `NFStatusNotify_tests.json#11` (`Invalid Content-Encoding Type`)
- Violated constraint: `The callback request may include a 'Content-Encoding' header of type string (Content-Encoding, described in IETF RFC 9110).`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `7/10`
- Why: The request declares Content-Encoding: gzip but the body is plain JSON. A server should attempt to decode and on failure return a 4xx (commonly 400 Bad Request or 415). open5gs returns 400 (cannot parse) which is reasonable. free5gc and oai return 404 Not Found, which is unexpected unless the callback URL is not implemented; if the endpoint exists, 404 is not the correct response for a malformed Content-Encoding header. Likely an implementation/configuration problem for free5gc and oai.

## NFStatusSubscribe

### Missing nfStatusNotificationUri
- Testcase: `NFStatusSubscribe_tests.json#0`, `NFStatusSubscribe_tests.json#1` (`Missing nfStatusNotificationUri`, `Missing nfStatusNotificationUri`)
- Violated constraint: `The nfStatusNotificationUri property is required in the SubscriptionData request body. / The request body MUST be present and MUST conform to the SubscriptionData schema.`
- Returns: `free5gc: 201; oai: 400; open5gs: 400`
- Confidence: `9/10`
- Why: free5gc accepted both missing-`nfStatusNotificationUri` variants and oai/open5gs rejected them. free5gc's behavior likely violates the SubscriptionData schema requirement.

### Invalid Content-Type Header
- Testcase: `NFStatusSubscribe_tests.json#2` (`Invalid Content-Type Header`)
- Violated constraint: `The request body content type for the subscription creation MUST be application/json.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: Request used Content-Type: text/plain. open5gs rejected, but free5gc and oai accepted and created subscriptions. The spec mandates application/json for subscription creation; accepting text/plain (parsing despite wrong header) is likely non-compliant, though some servers permissively parse body regardless of header.

### Subscription with empty sharedDataIds
- Testcase: `NFStatusSubscribe_tests.json#3` (`Subscription with empty sharedDataIds`)
- Violated constraint: `If sharedDataIds is present, it MUST be an array containing at least 1 item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: sharedDataIds was present as an empty array but the spec requires at least one item when present. free5gc and oai accepted (201); open5gs rejected. free5gc and oai likely violate the constraint by allowing an empty array.

### Invalid subscriptionId with hyphen
- Testcase: `NFStatusSubscribe_tests.json#4` (`Invalid subscriptionId with hyphen`)
- Violated constraint: `The subscriptionId property, when present, MUST match the regular expression '^([0-9]{5,6}-(x3Lf57A:nid=[A-Fa-f0-9]{11}:)?)?[^-]+$'.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: Client-provided subscriptionId ('invalid-sub-id') does not match the required regex. open5gs rejected the request, but free5gc and oai returned 201 (apparently ignoring/replacing the client id). The spec requires the property, when present, to conform; accepting/overriding an invalid client-provided id is likely non-compliant (though servers that ignore the field could argue permissive behavior).

### ReadOnly SubscriptionId
- Testcase: `NFStatusSubscribe_tests.json#5` (`Provide readOnly subscriptionId in request`)
- Violated constraint: `The subscriptionId property is readOnly and must not be provided by the client in the request.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: The client supplied the readOnly subscriptionId. open5gs rejects with 400 which aligns with a strict interpretation of the RFC. free5gc and oai returned 201 (creating a subscription) and produced their own subscriptionId (i.e. they appear to ignore/replace the client-supplied value). While some servers may permissively ignore readOnly fields, accepting a request that includes a field that 'must not be provided' is non‑strict behaviour and likely a spec violation in a strict test harness.

### Empty reqNotifEvents
- Testcase: `NFStatusSubscribe_tests.json#6` (`Invalid reqNotifEvents - empty array`)
- Violated constraint: `If reqNotifEvents is present, it MUST be an array and MUST contain at least 1 item, each item being one of the NotificationEventType enum values (e.g. NF_REGISTERED, NF_DEREGISTERED, NF_PROFILE_CHANGED, SHARED_DATA_CHANGED).`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: reqNotifEvents was sent as an empty array but the spec requires at least one item if present. open5gs returned 400 (correct), while free5gc and oai accepted and created a subscription (oai even echoed the empty array). Accepting empty arrays here is non‑compliant with the stated constraint and likely an implementation bug.

### Invalid reqSnssais Empty Array
- Testcase: `NFStatusSubscribe_tests.json#7` (`Invalid reqSnssais Empty Array`)
- Violated constraint: `If reqSnssais is present, it MUST be an array containing at least 1 ExtSnssai item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: reqSnssais was an empty array but the spec requires at least one ExtSnssai if present. open5gs rejected (400) which is correct. free5gc and oai accepted (201) — accepting an empty array where at least one item is required is likely a violation (oai even returned the empty array).

### Empty reqPerPlmnSnssais
- Testcase: `NFStatusSubscribe_tests.json#8` (`Invalid reqPerPlmnSnssais - empty array`)
- Violated constraint: `If reqPerPlmnSnssais is present, it MUST be an array containing at least 1 PlmnSnssai item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: reqPerPlmnSnssais was provided as an empty array though the spec requires at least one PlmnSnssai if present. open5gs returned 400 (expected). free5gc and oai returned 201 — permissive handling of an empty array is likely non‑compliant behavior.

### Empty reqPlmnList
- Testcase: `NFStatusSubscribe_tests.json#9` (`Empty reqPlmnList`)
- Violated constraint: `If reqPlmnList is present, it MUST be an array containing at least 1 PlmnId item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: reqPlmnList was an empty array but the spec mandates at least one PlmnId if present. open5gs rejected with 400 (appropriate). free5gc and oai accepted the request and created subscriptions — accepting an empty list where at least one element is required is likely a violation.

### Empty reqSnpnList (violates minItems)
- Testcase: `NFStatusSubscribe_tests.json#10` (`Empty reqSnpnList (violates minItems)`)
- Violated constraint: `If reqSnpnList is present, it MUST be an array containing at least 1 PlmnIdNid item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: reqSnpnList was sent as an empty array which violates the stated minItems constraint. free5gc and oai accepted (201) whereas open5gs rejected (400). Accepting an empty reqSnpnList is likely non‑compliant with the schema; oai also appears to auto-populate subscrCond on the server side. open5gs's rejection is the stricter/expected behavior.

### ServingScope Empty Array
- Testcase: `NFStatusSubscribe_tests.json#11` (`ServingScope Empty Array`)
- Violated constraint: `If servingScope is present, it MUST be an array containing at least 1 string item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: servingScope was sent as an empty array which violates the minItems constraint. free5gc and oai accepted (201) while open5gs rejected (400). Accepting an empty servingScope is likely a schema violation by free5gc/oai; open5gs's rejection is more correct.

### ReadOnly Features Provided
- Testcase: `NFStatusSubscribe_tests.json#12` (`Include readOnly nrfSupportedFeatures in request`)
- Violated constraint: `The requesterFeatures property is writeOnly and is defined by the SupportedFeatures schema, meaning it can be provided by the client in the request (but will not be returned in read responses).`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: requesterFeatures (writeOnly) may be supplied by client and can be accepted; however nrfSupportedFeatures (readOnly) must not be returned or should be rejected/ignored. free5gc accepted and echoed nrfSupportedFeatures back (violates readOnly semantics). oai accepted but did not echo (acceptable if it ignored the readOnly field). open5gs rejected the request (different stricter validation). free5gc behavior is likely non‑compliant.

### ReadOnly Features Echoed
- Testcase: `NFStatusSubscribe_tests.json#13` (`Provide readOnly nrfSupportedFeatures in subscription request`)
- Violated constraint: `The nrfSupportedFeatures property is readOnly and must not be provided by the client in the request.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: nrfSupportedFeatures is readOnly and must not be provided/echoed by the server. free5gc accepted and returned the field (violates readOnly). oai accepted but did not echo (acceptable if ignored). open5gs rejected. free5gc is likely non‑compliant.

### Empty extPreferredLocality
- Testcase: `NFStatusSubscribe_tests.json#14` (`Invalid extPreferredLocality Empty Object`)
- Violated constraint: `extPreferredLocality, when present, MUST be an object containing at least one property; each property value MUST be an array with at least one LocalityDescription item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: extPreferredLocality was sent as an empty object which violates the constraint (must have at least one property whose values are non‑empty arrays). free5gc and oai accepted (201) while open5gs returned 400. Accepting an empty extPreferredLocality appears to be a schema violation by free5gc/oai; open5gs's rejection is likely correct.

### Non-boolean completeProfileSubscription
- Testcase: `NFStatusSubscribe_tests.json#15` (`Non-boolean completeProfileSubscription`)
- Violated constraint: `completeProfileSubscription is a boolean with default false and writeOnly; providing a non-boolean value violates the schema.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The request supplies a non-boolean for completeProfileSubscription (schema requires boolean). free5gc and oai accept and create subscriptions (lenient behavior). open5gs returns 400. Accepting a type-mismatched property violates the schema/RFC; open5gs's rejection is the correct behavior.

### Invalid subscrCond variant
- Testcase: `NFStatusSubscribe_tests.json#16` (`Invalid subscrCond variant`)
- Violated constraint: `subscrCond, if present, MUST conform to one of the SubscrCond variants (oneOf): NfInstanceIdCond, NfInstanceIdListCond, NfTypeCond, ServiceNameCond, ServiceNameListCond, AmfCond, GuamiListCond, NetworkSliceCond, NfGroupCond, NfGroupListCond, NfSetCond, NfServiceSetCond, UpfCond, ScpDomainCond, NwdafCond, NefCond, or DccfCond.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The subscrCond does not match any allowed SubscrCond variant. free5gc and oai accept and echo the invalid structure (lenient), while open5gs rejects with 400. The server should validate against the oneOf variants and reject non-conforming subscrCond; free5gc and oai are likely violating the spec.

### Missing nfInstanceId for NfInstanceIdCond
- Testcase: `NFStatusSubscribe_tests.json#17` (`Missing nfInstanceId for NfInstanceIdCond`)
- Violated constraint: `If subscrCond is NfInstanceIdCond, the nfInstanceId property is required.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: ConditionType NfInstanceIdCond requires an nfInstanceId property. free5gc and oai accept a missing required field; open5gs rejects. Accepting a subscrCond missing required fields violates the spec/schema; open5gs behavior is correct.

### Empty NfInstanceIdList in SubscrCond
- Testcase: `NFStatusSubscribe_tests.json#18` (`Empty NfInstanceIdList in SubscrCond`)
- Violated constraint: `If subscrCond is NfInstanceIdListCond, the nfInstanceIdList property is required and it MUST contain at least 1 item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: nfInstanceIdList is provided empty but the schema requires at least one item. free5gc and oai accept the empty list (lenient), open5gs rejects. Allowing an empty required-list violates the schema requirement; open5gs is correct to return 400.

### Forbidden SubscrCond Field
- Testcase: `NFStatusSubscribe_tests.json#19` (`SubscrCond NfTypeCond with forbidden nfGroupId`)
- Violated constraint: `If subscrCond.conditionType is NfTypeCond, subscrCond.nfType is required and subscrCond must not include nfGroupId or the pair conditionType + nfGroupIdList. This test includes a forbidden nfGroupId.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: For NfTypeCond the subscrCond must not include nfGroupId (forbidden). free5gc and oai accept the forbidden field; open5gs rejects. Including forbidden fields where the spec disallows them is a protocol/schema violation—free5gc and oai are likely non-conformant.

### Missing serviceName for ServiceNameCond
- Testcase: `NFStatusSubscribe_tests.json#20` (`Missing serviceName for ServiceNameCond`)
- Violated constraint: `If subscrCond is ServiceNameCond, the serviceName property is required.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The request omits the required serviceName for a ServiceNameCond. open5gs rejects with 400 (enforcing the requirement). free5gc and oai accept (201) — free5gc even normalizes to empty strings. Accepting a subscription missing a required property violates the spec; differing behavior may be a lenient implementation but is non‑compliant.

### SubscrCond with empty serviceNameList
- Testcase: `NFStatusSubscribe_tests.json#21` (`SubscrCond with empty serviceNameList`)
- Violated constraint: `If subscrCond is ServiceNameListCond, serviceNameList MUST contain at least 1 item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The request supplies an empty serviceNameList while the spec mandates at least one item. open5gs correctly rejects (400). free5gc and oai accept (201) and return/echo an empty list. Accepting an empty required list is likely an RFC violation (leniency possible but non‑compliant).

### SubscrCond AmfCond without amfSetId
- Testcase: `NFStatusSubscribe_tests.json#22` (`SubscrCond AmfCond without amfSetId or amfRegionId`)
- Violated constraint: `If subscrCond is AmfCond, at least one of amfSetId or amfRegionId MUST be present.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The AmfCond lacks both amfSetId and amfRegionId though at least one is required. open5gs rejects (400). free5gc and oai accept (201). Accepting an AmfCond without any of the required identifiers is very likely a spec violation (implementation leniency unlikely to be correct).

### SubscrCond GuamiList Empty
- Testcase: `NFStatusSubscribe_tests.json#23` (`SubscrCond GuamiList Empty`)
- Violated constraint: `If subscrCond is GuamiListCond, guamiList is required and it MUST contain at least 1 item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The guamiListCond contains an empty guamiList while the spec requires at least one item. open5gs rejects (400). free5gc and oai accept (201) and echo an empty list or blank fields. Accepting an empty required list is likely non‑compliant behavior rather than acceptable variation.

### Empty NetworkSliceCond
- Testcase: `NFStatusSubscribe_tests.json#24` (`Invalid NetworkSliceCond with empty snssaiList and nsiList`)
- Violated constraint: `If subscrCond is NetworkSliceCond, snssaiList is required and it MUST contain at least 1 item; if nsiList is present it MUST contain at least 1 item.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The NetworkSliceCond provides empty snssaiList and nsiList though snssaiList must contain ≥1 item (and nsiList, if present, must be non‑empty). open5gs rejects (400). free5gc and oai accept (201). Accepting these empty lists likely violates the specification; this appears to be lenient but non‑compliant behavior.

### Forbidden NfType
- Testcase: `NFStatusSubscribe_tests.json#25` (`subscrCond nfGroupCond with forbidden nfType 'NRF'`)
- Violated constraint: `If subscrCond is NfGroupCond, both nfType and nfGroupId are required and nfType is restricted to the enum [UDM, AUSF, UDR, PCF, CHF, HSS, BSF, UDSF].`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The request uses a forbidden nfType value ('NRF') for an NfGroupCond. open5gs returns 400 which matches the constraint; free5gc and oai accept and return 201 (oai even echoes nfType='NRF'). Accepting a value explicitly excluded by the enum is likely an RFC non‑compliance (or overly lenient configuration) in free5gc/oai.

### Missing NfSetId
- Testcase: `NFStatusSubscribe_tests.json#27` (`Missing nfSetId when subscrCond is NfSetCond`)
- Violated constraint: `If subscrCond is NfSetCond, nfSetId is required.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The NfSetCond payload omits required nfSetId. open5gs rejects with 400 (correct per spec). free5gc and oai accept and create subscriptions despite the missing required field, which is likely a violation (lenient validation) of the constraint.

### Missing NfServiceSetId
- Testcase: `NFStatusSubscribe_tests.json#28` (`Missing nfServiceSetId when subscrCond is NfServiceSetCond`)
- Violated constraint: `If subscrCond is NfServiceSetCond, nfServiceSetId is required.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The NfServiceSetCond is missing required nfServiceSetId. open5gs returns 400 (appropriate). free5gc and oai accept the request and return 201, indicating they do not enforce the required-field rule — likely non‑compliant behavior or misconfiguration.

### Invalid UpfCond conditionType value
- Testcase: `NFStatusSubscribe_tests.json#29` (`Invalid UpfCond conditionType value`)
- Violated constraint: `If subscrCond is UpfCond, conditionType is required and MUST equal 'UPF_COND'.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: UpfCond requires conditionType='UPF_COND' but an invalid value was provided. open5gs rejects (400) which aligns with the constraint. free5gc and oai accept and create subscriptions with the invalid conditionType, which is likely an RFC violation (improper validation).

### Invalid NwdafCond conditionType
- Testcase: `NFStatusSubscribe_tests.json#30` (`Invalid NwdafCond conditionType`)
- Violated constraint: `If subscrCond is NwdafCond, conditionType is required and MUST equal 'NWDAF_COND'.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: NwdafCond requires conditionType='NWDAF_COND' but an invalid value was supplied. open5gs rejects with 400 (correct). free5gc and oai accept the invalid conditionType and return 201, indicating lax or missing validation and probable non‑compliance.

### Invalid NefCond Type
- Testcase: `NFStatusSubscribe_tests.json#31` (`subscrCond with incorrect conditionType for NefCond`)
- Violated constraint: `If subscrCond is NefCond, conditionType is required and MUST equal 'NEF_COND'.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The request includes nefCond but sets conditionType to 'INVALID_COND'. The spec requires conditionType == 'NEF_COND' when nefCond is present. open5gs rejects (400) which matches strict validation; free5gc and oai accept and create subscriptions, which is likely a permissive behavior and a deviation from the RFC (should be rejected). Possible explanation: implementations configured to be lenient, but this is likely non-compliant.

### Invalid DccfCond conditionType value
- Testcase: `NFStatusSubscribe_tests.json#32` (`Invalid DccfCond conditionType value`)
- Violated constraint: `If subscrCond is DccfCond, conditionType is required and MUST equal 'DCCF_COND'.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: The request includes dccfCond but uses conditionType 'INVALID_COND'. The spec mandates conditionType == 'DCCF_COND' for DccfCond. open5gs rejects (400) while free5gc and oai accept — the latter behavior is likely a violation of the normative requirement (or a deliberately permissive configuration), so probably non-compliant.

### Conflicting NotifCondition
- Testcase: `NFStatusSubscribe_tests.json#33` (`NotifCondition Contains Both Monitored and Unmonitored Attributes`)
- Violated constraint: `notifCondition, if present, MUST NOT contain both monitoredAttributes and unmonitoredAttributes at the same time.`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: The notifCondition contains both monitoredAttributes and unmonitoredAttributes, which the spec forbids. free5gc and oai accept and create subscriptions; open5gs returns 400 (though its message complains about missing subscrCond). Accepting this payload is likely non-compliant with the MUST constraint. It could be a lenient implementation choice, but it appears to violate the RFC.

### Invalid nfStatusNotificationUri format
- Testcase: `NFStatusSubscribe_tests.json#34` (`Invalid nfStatusNotificationUri format`)
- Violated constraint: `The nfStatusNotificationUri must be a valid absolute URI usable as the callback endpoint (the callback uses '{$request.body#/nfStatusNotificationUri}' to POST NotificationData).`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `8/10`
- Why: The nfStatusNotificationUri is not a valid absolute URI. The spec requires a valid URI usable for callbacks. free5gc and oai accept the invalid URI and create subscriptions; open5gs rejects (400) albeit with an unrelated message. Accepting an invalid callback URI is likely a spec violation (or a permissive/configuration difference).

## NFStatusUnsubscribe

### Missing SubscriptionId
- Testcase: `NFStatusUnsubscribe_tests.json#0` (`Missing SubscriptionId`)
- Violated constraint: `The 'subscriptionID' path parameter is required and must be provided.`
- Returns: `free5gc: 404; oai: 404; open5gs: 400`
- Confidence: `8/10`
- Why: free5gc and oai return 404 which is the expected semantics when the required path parameter is missing (resource/route not matched). open5gs returns a 400 "cannot parse HTTP message" which indicates it is treating a missing path as a malformed request rather than an unmatched route — that is likely incorrect behavior versus expected 404.

### Invalid subscriptionID containing hyphen
- Testcase: `NFStatusUnsubscribe_tests.json#1` (`Invalid subscriptionID containing hyphen`)
- Violated constraint: `The 'subscriptionID' path parameter must be a string matching the regular expression '^([0-9]{5,6}-(x3Lf57A:nid=[A-Fa-f0-9]{11}:)?)?[^-]+$'.`
- Returns: `free5gc: 204; oai: 404; open5gs: 400`
- Confidence: `7/10`
- Why: oai's 404 is reasonable for a non-existent/invalid subscription id. free5gc returning 204 (success) for a clearly invalid id (and one that should likely be rejected or reported not found) is suspicious. open5gs returning 400 parse error again looks like it failed to handle the path correctly. free5gc and open5gs behaviors are likely non-conformant.

### DELETE with Request Body
- Testcase: `NFStatusUnsubscribe_tests.json#2` (`DELETE with Request Body`)
- Violated constraint: `This DELETE operation does not define or accept a request body.`
- Returns: `free5gc: 204; oai: 404; open5gs: 400`
- Confidence: `6/10`
- Why: DELETE with an unexpected request body: servers may ignore an unused payload and proceed (free5gc's 204 can be acceptable), or return not-found if the id does not exist (oai's 404). open5gs returning 400 with "cannot parse HTTP message" suggests a parsing/implementation error rather than a deliberate semantic rejection of a body—this is likely an implementation bug.

## NFUpdate

### Invalid NFInstanceId
- Testcase: `NFUpdate_tests.json#0` (`Invalid NFInstanceId`)
- Violated constraint: `The path parameter must be a valid NfInstanceId.`
- Returns: `free5gc: 200; oai: 200; open5gs: 201`
- Confidence: `9/10`
- Why: All implementations accepted/updated the NF instance even though the path parameter 'not-a-uuid' is not a valid NfInstanceId. The NRF spec requires the nfInstanceId path parameter to be a valid UUID and a server should reject an invalid identifier (4xx). Accepting a non-UUID path (even if the body contains a valid nfInstanceId) is likely non‑compliant. Possible but unlikely explanation: the servers treat the body nfInstanceId as authoritative or do not validate path format.

### Empty plmnList
- Testcase: `NFUpdate_tests.json#7` (`Invalid plmnList - empty array`)
- Violated constraint: `If present, 'plmnList' must be an array with at least 1 item and each item must conform to TS29571_CommonData.yaml#/components/schemas/PlmnId.`
- Returns: `free5gc: 200; oai: 200; open5gs: 400`
- Confidence: `8/10`
- Why: free5gc and oai returned success despite an empty plmnList, whereas open5gs returned 400. The spec requires plmnList, if present, to contain at least one item. Accepting an empty array is likely a protocol violation by free5gc and oai (though it could be a configurable leniency to ignore empty arrays).

### Empty allowedNfTypes
- Testcase: `NFUpdate_tests.json#16` (`Invalid allowedNfTypes - empty array`)
- Violated constraint: `If present, 'allowedNfTypes' must be an array with at least 1 item and each item must conform to '#/components/schemas/NFType'.`
- Returns: `free5gc: 200; oai: 200; open5gs: 400`
- Confidence: `8/10`
- Why: free5gc and oai accepted an empty allowedNfTypes array while open5gs rejected with 400. The spec requires allowedNfTypes, if present, to have at least one item. Accepting an empty array is likely non‑compliant (possibly a permissive implementation behavior/config option).

### Empty Vendor Features
- Testcase: `NFUpdate_tests.json#31` (`Invalid supportedVendorSpecificFeatures value (empty array)`)
- Violated constraint: `If present, 'supportedVendorSpecificFeatures' must be an object with at least 1 property; each value must be an array with at least 1 VendorSpecificFeature item.`
- Returns: `free5gc: 200; oai: 200; open5gs: 400`
- Confidence: `8/10`
- Why: free5gc and oai accepted supportedVendorSpecificFeatures where a vendor key maps to an empty array; open5gs rejected with 400. The spec requires each value array to contain at least one VendorSpecificFeature. Accepting empty arrays here is likely a violation by free5gc and oai (or a deliberate lenient/configurable parsing choice).
