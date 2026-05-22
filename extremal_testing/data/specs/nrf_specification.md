# API Spec

2. On success, "200 OK" shall be returned, the payload body of the POST response shall contain the requested access token and the token type set to value "Bearer". The response in addition:

- should contain the expiration time for the token as indicated in IETF RFC 6749 [16] unless the expiration time of the token is made available by other means (e.g. deployment-specific documentation); and

- shall contain the NF service name of the requested NF service producer, if it is different from the scope included in the access token request (see IETF RFC 6749 [16]).

The access token shall be a JSON Web Token (JWT) as specified in IETF RFC 7519 [25]. The access token returned by the NRF shall include the claims encoded as a JSON object as specified in subclause 6.3.5.2.4 and then digitally signed using JWS as specified in IETF RFC 7515 [24] and in subclause 13.4.1 of 3GPP TS 33.501 [15].

The digitally signed access token shall be converted to the JWS Compact Serialization encoding as a string as specified in clause 7.1 of IETF RFC 7515 [24].

If the access token request fails at the NRF, the NRF shall return "400 Bad Request" status code, including in the response payload a JSON object that provides details about the specific error that occurred.

6 API Definitions

## 6.1 Nnrf_NFManagement Service API

### 6.1.1 API URI

URIs of this API shall have the following root:

{apiRoot}/{apiName}/{apiVersion}/

where "apiRoot" is defined in subclause 4.4.1 of 3GPP TS 29.501 [5], the "apiName" shall be set to "nnrf-nfm" and the "apiVersion" shall be set to "v1" for the current version of this specification.

### 6.1.2 Usage of HTTP

#### 6.1.2.1 General

HTTP/2, as defined in IETF RFC 7540 [9], shall be used as specified in clause 5 of 3GPP TS 29.500 [4].

HTTP/2 shall be transported as specified in subclause 5.3 of 3GPP TS 29.500 [4].

HTTP messages and bodies for the Nnrf_NFManagement service shall comply with the OpenAPI [10] specification contained in Annex A.

#### 6.1.2.2 HTTP Standard Headers

##### 6.1.2.2.1 General

##### 6.1.2.2.2 Content type

The following content types shall be supported:

- JSON, as defined in IETF RFC 8259 [22], shall be used as content type of the HTTP bodies specified in the present specification as indicated in subclause 5.4 of 3GPP TS 29.500 [4].

- The Problem Details JSON Object (IETF RFC 7807 [11]). The use of the Problem Details JSON object in a HTTP response body shall be signalled by the content type "application/problem+json".

- JSON Patch (IETF RFC 6902 [13]). The use of the JSON Patch format in a HTTP request body shall be signalled by the content type "application/json-patch+json".

- The 3GPP hypermedia format as defined in 3GPP TS 29.501 [5]. The use of the 3GPP hypermedia format in a HTTP response body shall be signalled by the content type "application/3gppHal+json".

#### 6.1.2.3 HTTP custom headers

##### 6.1.2.3.1 General

In this release of this specification, no custom headers specific to the Nnrf_NFManagement service are defined. For 3GPP specific HTTP custom headers used across all service-based interfaces, see subclause 5.2.3 of 3GPP TS 29.500 [4].

### 6.1.3 Resources

#### 6.1.3.1 Overview

The structure of the Resource URIs of the NFManagement service is shown in figure 6.1.3.1-1.

{apiRoot}/nnrf-nfm/v1

/nf-instances

/{nfInstanceID}

/subscriptions

/{subscriptionID}

Figure 6.1.3.1-1: Resource URI structure of the NFManagement API

### Table 6.1.3.1-1 provides an overview of the resources and applicable HTTP methods.

### Table 6.1.3.1-1: Resources and methods overview
| Resource name | Resource URI | HTTP method or custom operation | Description |
| --- | --- | --- | --- |
| nf-instances (Store) | `{apiRoot}/nnrf-nfm/v1/nf-instances` | GET | Read a collection of NF Instances. |
| nf-instance (Document) | `{apiRoot}/nnrf-nfm/v1/nf-instances/{nfInstanceID}` | GET | Read the profile of a given NF Instance. |
| nf-instance (Document) | `{apiRoot}/nnrf-nfm/v1/nf-instances/{nfInstanceID}` | PUT | Register in NRF a new NF Instance, or replace the profile of an existing NF Instance, by providing an NF profile. |
| nf-instance (Document) | `{apiRoot}/nnrf-nfm/v1/nf-instances/{nfInstanceID}` | PATCH | Modify the NF profile of an existing NF Instance. |
| nf-instance (Document) | `{apiRoot}/nnrf-nfm/v1/nf-instances/{nfInstanceID}` | DELETE | Deregister from NRF a given NF Instance. |
| subscriptions (Collection) | `{apiRoot}/nnrf-nfm/v1/subscriptions` | POST | Creates a new subscription in NRF to newly registered NF Instances. |
| subscription (Document) | `{apiRoot}/nnrf-nfm/v1/subscriptions/{subscriptionID}` | PATCH | Updates an existing subscription in NRF. |
| subscription (Document) | `{apiRoot}/nnrf-nfm/v1/subscriptions/{subscriptionID}` | DELETE | Deletes an existing subscription from NRF. |
| NF Status Notification | `{nfStatusNotificationUri}` | POST | Notify about newly created NF Callback Instances, or about changes of the profile of a given NF Instance. |

#### 6.1.3.2 Resource: nf-instances (Store)

##### 6.1.3.2.1 Description

This resource represents a collection of the different NF instances registered in the NRF.

This resource is modelled as the Store resource archetype (see subclause C.3 of 3GPP TS 29.501 [5]).

##### 6.1.3.2.2 Resource Definition

Resource URI: {apiRoot}/nnrf-nfm/v1/nf-instances

This resource shall support the resource URI variables defined in table 6.1.3.2.2-1.

### Table 6.1.3.2.2-1: Resource URI variables for this resource
| Name | Description |
| --- | --- |
| apiRoot | See subclause 6.1.1 |

##### 6.1.3.2.3 Resource Standard Methods

###### 6.1.3.2.3.1 GET

This method retrieves a list of all NF instances currently registered in the NRF. This method shall support the URI query parameters specified in table 6.1.3.2.3.1-1.

### Table 6.1.3.2.3.1-1: URI query parameters supported by the GET method on this resource
| Name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| nf-type | NFType | 0..1 | The type of NF to restrict the list of returned NF Instances. |
| limit | integer | 0..1 | Maximum number of items to be returned in this query. |

This method shall support the request data structures specified in table 6.1.3.2.3.1-2 and the response data structures and response codes specified in table 6.1.3.2.3.1-3.

### Table 6.1.3.2.3.1-2: Data structures supported by the GET Request Body on this resource
No request body data structures are defined for this method.

### Table 6.1.3.2.3.1-3: Data structures supported by the GET Response Body on this resource
| Data type | Cardinality | Response code | Description |
| --- | --- | --- | --- |
| UriList | 1 | 200 OK | The response body contains a "_links" object containing the URI of each registered NF in the NRF, or an empty object if there are no NFs to return in the query result (e.g., because there are no registered NFs in the NRF, or because there are no matching NFs of the type specified in the "nf-type" query parameter, currently registered in the NRF). |

NOTE: The mandatory HTTP error status codes for the GET method listed in Table 5.2.7.1-1 of 3GPP TS 29.500 [4] other than those specified in the table above also apply, with a ProblemDetails data type (see subclause 5.2.7 of 3GPP TS 29.500 [4]).

##### 6.1.3.2.4 Resource Custom Operations

There are no resource custom operations for the Nnrf_NFManagement service in this release of the specification.

#### 6.1.3.3 Resource: nf-instance (Document)

##### 6.1.3.3.1 Description

This resource represents a single NF instance.

##### 6.1.3.3.2 Resource Definition

Resource URI: {apiRoot}/nnrf-nfm/v1/nf-instances/{nfInstanceID}

This resource shall support the resource URI variables defined in table 6.1.3.3.2-1.

### Table 6.1.3.3.2-1: Resource URI variables for this resource
| Name | Description |
| --- | --- |
| apiRoot | See subclause 6.1.1 |
| nfInstanceID | Represents a specific NF Instance |

##### 6.1.3.3.3 Resource Standard Methods

###### 6.1.3.3.3.1 GET

This method retrieves the NF Profile of a given NF instance.

This method shall support the URI query parameters specified in table 6.1.3.3.3.1-1.

### Table 6.1.3.3.3.1-1: URI query parameters supported by the GET method on this resource
No query parameters are defined for this method.

This method shall support the request data structures specified in table 6.1.3.3.3.1-2 and the response data structures and response codes specified in table 6.1.3.3.3.1-3.

### Table 6.1.3.3.3.1-2: Data structures supported by the GET Request Body on this resource
No request body data structures are defined for this method.

### Table 6.1.3.3.3.1-3: Data structures supported by the GET Response Body on this resource
| Data type | Cardinality | Response code | Description |
| --- | --- | --- | --- |
| NFProfile | 1 | 200 OK | The response body contains the profile of a given NF Instance. |

NOTE: The mandatory HTTP error status codes for the GET method listed in Table 5.2.7.1-1 of 3GPP TS 29.500 [4] other than those specified in the table above also apply, with a ProblemDetails data type (see subclause 5.2.7 of 3GPP TS 29.500 [4]).

###### 6.1.3.3.3.2 PUT

This method registers a new NF instance in the NRF, or replaces completely an existing NF instance.

This method shall support the URI query parameters specified in table 6.1.3.3.3.2-1.

### Table 6.1.3.3.3.2-1: URI query parameters supported by the PUT method on this resource
No query parameters are defined for this method.

This method shall support the request data structures specified in table 6.1.3.3.3.2-2 and the response data structures and response codes specified in table 6.1.3.3.3.2-3.

### Table 6.1.3.3.3.2-2: Data structures supported by the PUT Request Body on this resource
| Data type | Cardinality | Description |
| --- | --- | --- |
| NFProfile | 1 | Profile of the NF Instance to be registered, or completely replaced, in NRF. |

### Table 6.1.3.3.3.2-3: Data structures supported by the PUT Response Body on this resource
| Data type | Cardinality | Response code | Description |
| --- | --- | --- | --- |
| NFProfile | 1 | 200 OK | This case represents the successful replacement of an existing NF Instance profile. |
| NFProfile | 1 | 201 Created | This case represents the successful registration of a new NF Instance. Upon success, a response body is returned containing the newly created NF Instance profile; also, the HTTP response shall include a "Location" HTTP header that contains the resource URI of the created NF Instance. |

NOTE: The mandatory HTTP error status codes for the PUT method listed in Table 5.2.7.1-1 of 3GPP TS 29.500 [4] other than those specified in the table above also apply, with a ProblemDetails data type (see subclause 5.2.7 of 3GPP TS 29.500 [4]).

###### 6.1.3.3.3.3 PATCH

This method updates partially the profile of a given NF instance.

This method shall support the URI query parameters specified in table 6.1.3.3.3.3-1.

### Table 6.1.3.3.3.3-1: URI query parameters supported by the PATCH method on this resource
No query parameters are defined for this method.

This method shall support the request data structures specified in table 6.1.3.3.3.3-2 and the response data structures and response codes specified in table 6.1.3.3.3.3-3.

### Table 6.1.3.3.3.3-2: Data structures supported by the PATCH Request Body on this resource
| Data type | Cardinality | Description |
| --- | --- | --- |
| PatchDocument | 1 | It contains the list of changes to be made to the profile of the NF Instance, according to the JSON PATCH format specified in IETF RFC 6902 [13]. |

### Table 6.1.3.3.3.3-3: Data structures supported by the PATCH Response Body on this resource
| Data type | Cardinality | Response code | Description |
| --- | --- | --- | --- |
| NFProfile | 1 | 200 OK | Upon success, a response body is returned containing the updated profile of the NF Instance. |
| n/a |  | 204 No Content | Successful response sent when there is no need to provide a full updated profile of the NF Instance (e.g., in the Heart-Beat operation response described in subclause 5.2.2.3.2). |

NOTE: The mandatory HTTP error status codes for the PATCH method listed in Table 5.2.7.1-1 of 3GPP TS 29.500 [4] other than those specified in the table above also apply, with a ProblemDetails data type (see subclause 5.2.7 of 3GPP TS 29.500 [4]).

###### 6.1.3.3.3.4 DELETE

This method deregisters an existing NF instance from the NRF.

This method shall support the URI query parameters specified in table 6.1.3.3.3.4-1.

### Table 6.1.3.3.3.4-1: URI query parameters supported by the DELETE method on this resource
No query parameters are defined for this method.

This method shall support the request data structures specified in table 6.1.3.3.3.4-2 and the response data structures and response codes specified in table 6.1.3.3.3.4-3.

### Table 6.1.3.3.3.4-2: Data structures supported by the DELETE Request Body on this resource
No request body data structures are defined for this method.

### Table 6.1.3.3.3.4-3: Data structures supported by the DELETE Response Body on this resource
| Data type | Cardinality | Response code | Description |
| --- | --- | --- | --- |
| n/a |  | 204 No Content | No response body is defined. |

NOTE: The mandatory HTTP error status codes for the PUT method listed in Table 5.2.7.1-1 of 3GPP TS 29.500 [4] other than those specified in the table above also apply, with a ProblemDetails data type (see subclause 5.2.7 of 3GPP TS 29.500 [4]).

#### 6.1.3.4 Resource: subscriptions (Collection)

##### 6.1.3.4.1 Description

This resource represents a collection of subscriptions of NF Instances to newly registered NF Instances.

##### 6.1.3.4.2 Resource Definition

Resource URI: {apiRoot}/nnrf-nfm/v1/subscriptions

This resource shall support the resource URI variables defined in table 6.1.3.4.2-1.

### Table 6.1.3.4.2-1: Resource URI variables for this resource
| Name | Description |
| --- | --- |
| apiRoot | See subclause 6.1.1 |

##### 6.1.3.4.3 Resource Standard Methods

###### 6.1.3.4.3.1 POST

This method creates a new subscription. This method shall support the URI query parameters specified in table 6.1.3.4.3.1-1.

### Table 6.1.3.4.3.1-1: URI query parameters supported by the POST method on this resource
No query parameters are defined for this method.

This method shall support the request data structures specified in table 6.1.3.4.3.1-2 and the response data structures and response codes specified in table 6.1.3.4.3.1-3.

### Table 6.1.3.4.3.1-2: Data structures supported by the POST Request Body on this resource
| Data type | Cardinality | Description |
| --- | --- | --- |
| SubscriptionData | 1 | The request body contains the input parameters for the subscription. These parameters include, e.g.: Target NF type; Target Service Name; Callback URI of the Requester NF. |

### Table 6.1.3.4.3.1-3: Data structures supported by the POST Response Body on this resource
| Data type | Cardinality | Response code | Description |
| --- | --- | --- | --- |
| SubscriptionData | 1 | 201 Created | This case represents the successful creation of a subscription. |

Upon success, the HTTP response shall include a "Location" HTTP header that contains the resource URI of the created resource. NOTE: The mandatory HTTP error status codes for the PUT method listed in Table 5.2.7.1-1 of 3GPP TS 29.500 [4] other than those specified in the table above also apply, with a ProblemDetails data type (see subclause 5.2.7 of 3GPP TS 29.500 [4]).

#### 6.1.3.5 Resource: subscription (Document)

##### 6.1.3.5.1 Description

This resource represents an individual subscription of a given NF Instance to newly registered NF Instances.

##### 6.1.3.5.2 Resource Definition

Resource URI: {apiRoot}/nnrf-nfm/v1/subscriptions/{subscriptionID}

This resource shall support the resource URI variables defined in table 6.1.3.5.2-1.

### Table 6.1.3.5.2-1: Resource URI variables for this resource
| Name | Description |
| --- | --- |
| apiRoot | See subclause 6.1.1 |
| subscriptionID | Represents a specific subscription |

##### 6.1.3.5.3 Resource Standard Methods

###### 6.1.3.5.3.1 DELETE

This method terminates an existing subscription. This method shall support the URI query parameters specified in table 6.1.3.5.3.1-1.

### Table 6.1.3.5.3.1-1: URI query parameters supported by the DELETE method on this resource
No query parameters are defined for this method.

This method shall support the request data structures specified in table 6.1.3.5.3.1-2 and the response data structures and response codes specified in table 6.1.3.5.3.1-3.

### Table 6.1.3.5.3.1-2: Data structures supported by the DELETE Request Body on this resource
No request body data structures are defined for this method.

### Table 6.1.3.5.3.1-3: Data structures supported by the DELETE Response Body on this resource
| Data type | Cardinality | Response code | Description |
| --- | --- | --- | --- |
| n/a |  | 204 No Content | No response body is defined. |

NOTE: The mandatory HTTP error status codes for the PUT method listed in Table 5.2.7.1-1 of 3GPP TS 29.500 [4] other than those specified in the table above also apply, with a ProblemDetails data type (see subclause 5.2.7 of 3GPP TS 29.500 [4]).

###### 6.1.3.5.3.2 PATCH

This method updates an existing subscription. This method shall support the URI query parameters specified in table 6.1.3.5.3.2-1.

### Table 6.1.3.5.3.2-1: URI query parameters supported by the PATCH method on this resource
No query parameters are defined for this method.

This method shall support the request data structures specified in table 6.1.3.5.3.2-2 and the response data structures and response codes specified in table 6.1.3.5.3.2-3.

### Table 6.1.3.5.3.2-2: Data structures supported by the PATCH Request Body on this resource
| Data type | Cardinality | Description |
| --- | --- | --- |
| array(PatchItem) | 1..N | It contains the list of changes to be made to the profile of the NF Instance, according to the JSON PATCH format specified in IETF RFC 6902 [13]. |

### Table 6.1.3.5.3.2-3: Data structures supported by the PATCH Response Body on this resource
| Data type | Cardinality | Response code | Description |
| --- | --- | --- | --- |
| SubscriptionData | 1 | 200 OK | |
| n/a |  | 204 No Content | |

### 6.1.4 Custom Operations without associated resources

There are no custom operations defined without any associated resources for the Nnrf_NFManagement service in this release of the specification.

### 6.1.5 Notifications

#### 6.1.5.1 General

This subclause specifies the notifications provided by the Nnrf_NFManagement service.

The delivery of notifications shall be supported as specified in subclause 6.2 of 3GPP TS 29.500 [4] for Server-initiated communication.

### Table 6.1.5.1-1: Notifications overview
| HTTP method | Description | Notification Resource URI or custom operation |
| --- | --- | --- |
| POST | Notify about NF Instance registrations, status deregistrations, or profile changes of NF Instances. | `{nfStatusNotificationUri}` (NF Service Consumer provided callback reference) |

#### 6.1.5.2 NF Instance Status Notification

##### 6.1.5.2.1 Description

The NF Service Consumer provides a callback URI for getting notified about NF Instances status events, the NRF shall notify the NF Service Consumer, when the conditions specified in the subscription are met.

##### 6.1.5.2.2 Notification Definition

The POST method shall be used for NF Instance Status notification and the URI shall be the callback reference provided by the NF Service Consumer during the subscription to this notification.

Resource URI: {nfStatusNotificationUri}

Support of URI query parameters is specified in table 6.1.5.2.2-1.

### Table 6.1.5.2.2-1: URI query parameters supported by the POST method
No query parameters are defined for this method.

Support of request data structures is specified in table 6.1.5.2.2-2, and support of response data structures and response codes is specified in table 6.1.5.2-3.

### Table 6.1.5.2.2-2: Data structures supported by the POST Request Body
| Data type | Cardinality | Description |
| --- | --- | --- |
| NotificationData | 1 | Representation of the NF Instance status notification. |

### Table 6.1.5.2.2-3: Data structures supported by the POST Response Body
| Data type | Cardinality | Response code | Description |
| --- | --- | --- | --- |
| n/a |  | 204 No Content | This case represents a successful notification of the NF Instance status event. |

NOTE: The mandatory HTTP error status codes for the PUT method listed in Table 5.2.7.1-1 of 3GPP TS 29.500 [4] other than those specified in the table above also apply, with a ProblemDetails data type (see subclause 5.2.7 of 3GPP TS 29.500 [4]).

### 6.1.6 Data Model

#### 6.1.6.1 General

This subclause specifies the application data model supported by the API.

### Table 6.1.6.1-1 specifies the data types defined for the Nnrf service based interface protocol.

### Table 6.1.6.1-1: Nnrf_NFManagement specific Data Types
| Data type | Section defined | Description |
| --- | --- | --- |
| NFProfile | 6.1.6.2.2 |  |
| NFService | 6.1.6.2.3 |  |
| DefaultNotificationSubscription | 6.1.6.2.4 | Data structure for specifying the notifications the NF service subscribes by default along with callback URI. |
| IpEndPoint | 6.1.6.2.5 |  |
| UdrInfo | 6.1.6.2.6 |  |
| UdmInfo | 6.1.6.2.7 |  |
| AusfInfo | 6.1.6.2.8 |  |
| SupiRange | 6.1.6.2.9 |  |
| IdentityRange | 6.1.6.2.10 |  |
| AmfInfo | 6.1.6.2.11 |  |
| SmfInfo | 6.1.6.2.12 |  |
| UpfInfo | 6.1.6.2.13 | Information related to UPF |
| SnssaiUpfInfoItem | 6.1.6.2.14 |  |
| DnnUpfInfoItem | 6.1.6.2.15 |  |
| SubscriptionData | 6.1.6.2.16 |  |
| NotificationData | 6.1.6.2.17 |  |
| NFServiceVersion | 6.1.6.2.19 | Contains the version details of an NF service. |
| PcfInfo | 6.1.6.2.20 |  |
| BsfInfo | 6.1.6.2.21 |  |
| Ipv4AddressRange | 6.1.6.2.22 |  |
| Ipv6PrefixRange | 6.1.6.2.23 |  |
| InterfaceUpfInfoItem | 6.1.6.2.24 |  |
| UriList | 6.1.6.2.25 |  |
| N2InterfaceAmfInfo | 6.1.6.2.26 | AMF N2 interface information |
| TaiRange | 6.1.6.2.27 |  |
| TacRange | 6.1.6.2.28 |  |
| SnssaiSmfInfoItem | 6.1.6.2.29 |  |
| DnnSmfInfoItem | 6.1.6.2.30 |  |
| NrfInfo | 6.1.6.2.31 |  |
| ChfInfo | 6.1.6.2.32 |  |
| ChfServiceInfo | 6.1.6.2.33 |  |
| PlmnRange | 6.1.6.2.34 |  |
| SubscrCond | 6.1.6.2.35 |  |
| NfInstanceIdCond | 6.1.6.2.36 |  |
| NfTypeCond | 6.1.6.2.37 |  |
| ServiceNameCond | 6.1.6.2.38 |  |
| AmfCond | 6.1.6.2.39 |  |
| GuamiListCond | 6.1.6.2.40 |  |
| NetworkSliceCond | 6.1.6.2.41 |  |
| NfGroupCond | 6.1.6.2.42 |  |
| NotifCondition | 6.1.6.2.43 |  |
| PlmnSnssai | 6.1.6.2.44 |  |
| Fqdn | 6.1.6.3.2 |  |
| NFType | 6.1.6.3.3 |  |
| NotificationType | 6.1.6.3.4 |  |
| TransportProtocol | 6.1.6.3.5 |  |
| NotificationEventType | 6.1.6.3.6 |  |
| NFStatus | 6.1.6.3.7 |  |
| DataSetId | 6.1.6.3.8 |  |
| UPInterfaceType | 6.1.6.3.9 |  |
| ServiceName | 6.1.6.3.11 |  |
| NFServiceStatus | 6.1.6.3.12 |  |

### Table 6.1.6.1-2 specifies data types re-used by the Nnrf service based interface protocol from other specifications,
including a reference to their respective specifications and when needed, a short description of their use within the Nnrf service based interface.

### Table 6.1.6.1-2: Nnrf_NFManagement re-used Data Types
| Data type | Reference | Comments |
| --- | --- | --- |
| N1MessageClass | 3GPP TS 29.518 [6] | The N1 message type |
| N2InformationClass | 3GPP TS 29.518 [6] | The N2 information type |
| IPv4Addr | 3GPP TS 29.571 [7] |  |
| IPv6Addr | 3GPP TS 29.571 [7] |  |
| IPv6Prefix | 3GPP TS 29.571 [7] |  |
| Uri | 3GPP TS 29.571 [7] |  |
| Dnn | 3GPP TS 29.571 [7] |  |
| SupportedFeatures | 3GPP TS 29.571 [7] |  |
| Snssai | 3GPP TS 29.571 [7] |  |
| PlmnId | 3GPP TS 29.571 [7] |  |
| Guami | 3GPP TS 29.571 [7] |  |
| Tai | 3GPP TS 29.571 [7] |  |
| NfInstanceId | 3GPP TS 29.571 [7] |  |
| LinksValueSchema | 3GPP TS 29.571 [7] | 3GPP Hypermedia link |
| UriScheme | 3GPP TS 29.571 [7] |  |
| AmfName | 3GPP TS 29.571 [7] |  |
| DateTime | 3GPP TS 29.571 [7] |  |
| Dnai | 3GPP TS 29.571 [7] |  |
| ChangeItem | 3GPP TS 29.571 [7] |  |
| DiameterIdentity | 3GPP TS 29.571 [7] |  |
| AccessType | 3GPP TS 29.571 [7] |  |
| NfGroupId | 3GPP TS 29.571 [7] | Network Function Group Id |
| AmfRegionId | 3GPP TS 29.571 [7] |  |
| AmfSetId | 3GPP TS 29.571 [7] |  |
| PduSessionType | 3GPP TS 29.571 [7] |  |

#### 6.1.6.2 Structured data types

##### 6.1.6.2.1 Introduction

This subclause defines the structures to be used in resource representations.

##### 6.1.6.2.2 Type: NFProfile

### Table 6.1.6.2.2-1: Definition of type NFProfile
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| nfInstanceID | NfInstanceId | 1 | Unique identity of the NF Instance. |
| nfType | NFType | 1 | Type of Network Function. |
| nfStatus | NFStatus | 1 | Status of the NF Instance. |
| heartBeatTimer | integer | 0..1 | Time in seconds expected between heart-beat messages from an NF Instance to the NRF. |
| plmnList | array(PlmnId) | 1..N | PLMN(s) of the Network Function. |
| sNssais | array(Snssai) | 1..N | S-NSSAIs of the Network Function. |
| perPlmnSnssaiList | array(PlmnSnssai) | 1..N | Per-PLMN list of S-NSSAI(s) supported by the Network Function. |
| nsiList | array(string) | 1..N | NSI identities of the Network Function. |
| fqdn | Fqdn | 0..1 | FQDN of the Network Function. |
| interPlmnFqdn | Fqdn | 0..1 | FQDN used for inter-PLMN routing. |
| ipv4Addresses | array(Ipv4Addr) | 1..N | IPv4 address(es) of the Network Function. |
| ipv6Addresses | array(Ipv6Addr) | 1..N | IPv6 address(es) of the Network Function. |
| allowedPlmns | array(PlmnId) | 1..N | PLMNs allowed to access the NF instance. |
| allowedNfTypes | array(NFType) | 1..N | Types of NFs allowed to access the NF instance. |
| allowedNfDomains | array(string) | 1..N | NF domain names allowed to access the NF instance. |
| allowedNssais | array(Snssai) | 1..N | S-NSSAIs of the allowed slices to access the NF instance. |
| priority | integer | 0..1 | Priority used for NF selection. |
| capacity | integer | 0..1 | Static capacity information used for NF selection. |
| load | integer | 0..1 | Dynamic load information. |
| locality | string | 0..1 | Operator-defined information about the NF location. |
| udrInfo | UdrInfo | 0..1 | Specific data for the UDR. |
| udmInfo | UdmInfo | 0..1 | Specific data for the UDM. |
| ausfInfo | AusfInfo | 0..1 | Specific data for the AUSF. |
| amfInfo | AmfInfo | 0..1 | Specific data for the AMF. |
| smfInfo | SmfInfo | 0..1 | Specific data for the SMF. |
| upfInfo | UpfInfo | 0..1 | Specific data for the UPF. |
| pcfInfo | PcfInfo | 0..1 | Specific data for the PCF. |
| bsfInfo | BsfInfo | 0..1 | Specific data for the BSF. |
| chfInfo | ChfInfo | 0..1 | Specific data for the CHF. |
| nrfInfo | NrfInfo | 0..1 | Specific data for the NRF. |
| customInfo | object | 0..1 | Specific data for custom Network Functions. |
| recoveryTime | DateTime | 0..1 | Timestamp when the NF was (re)started. |
| nfServicePersistence | boolean | 0..1 | Indicates that service instances can persist resource state in shared storage. |
| nfServices | array(NFService) | 1..N | List of NF Service Instances. |
| nfProfileChangesSupportedInd | boolean | 0..1 | NF Profile Changes Support Indicator. |
| nfProfileChangesInd | boolean | 0..1 | NF Profile Changes Indicator. |
| defaultNotificationSubscriptions | array(DefaultNotificationSubscription) | 1..N | Notification endpoints for different notification types. |

NOTE 1: At least one of the addressing parameters (fqdn, ipv4address or ipv6adress) shall be included in the NF Profile.
NOTE 2: If the type of Network Function is UPF, the addressing information is for the UPF N4 interface.
NOTE 3: A requester NF may use this information to select a NF instance.
NOTE 4: The capacity and priority parameters, if present, are used for NF selection and load balancing.
NOTE 5: The NRF shall notify NFs subscribed to receiving notifications of changes of the NF profile, if the NF recoveryTime or the nfStatus is changed.
NOTE 6: A requester NF may consider that all the resources created in the NF before the NF recovery time have been lost.
NOTE 7: A NF may register multiple PLMN IDs in its profile within a PLMN comprising multiple PLMN IDs.
NOTE 8: Other NFs are in a different PLMN if they belong to none of the PLMN ID(s) configured for the PLMN of the NRF.
NOTE 9: This is for the use case where an NF supports multiple PLMNs and the slices supported in each PLMN are different.
NOTE 10: If notification endpoints are present both in the profile of the NF instance and in some of its NF Services for a same notification type, the NF Service notification endpoint(s) shall be used.

##### 6.1.6.2.3 Type: NFService

### Table 6.1.6.2.3-1: Definition of type NFService
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| serviceInstanceID | string | 1 | Unique ID of the service instance within a given NF Instance. |
| serviceName | ServiceName | 1 | Name of the service instance. |
| versions | array(NFServiceVersion) | 1..N | API versions supported by the NF Service and, if available, the corresponding retirement date. |
| scheme | UriScheme | 1 | URI scheme. |
| nfServiceStatus | NFServiceStatus | 1 | Status of the NF Service Instance. |
| fqdn | Fqdn | 0..1 | FQDN of the NF Service Instance. |
| interPlmnFqdn | Fqdn | 0..1 | FQDN used for inter-PLMN routing. |
| ipEndPoints | array(IpEndPoint) | 1..N | IP address(es) and port information of the Network Function where the service is listening. |
| apiPrefix | string | 0..1 | Optional path segment(s) used to construct the apiRoot variable. |
| defaultNotificationSubscriptions | array(DefaultNotificationSubscription) | 1..N | Notification endpoints for different notification types. |
| allowedPlmns | array(PlmnId) | 1..N | PLMNs allowed to access the service instance. |
| allowedNfTypes | array(NFType) | 1..N | NF types allowed to access the service instance. |
| allowedNfDomains | array(string) | 1..N | NF domain names allowed to access the service instance. |
| allowedNssais | array(Snssai) | 1..N | S-NSSAIs allowed to access the service instance. |
| priority | integer | 0..1 | Priority used for NF Service selection. |
| capacity | integer | 0..1 | Static capacity information used for NF Service selection. |
| load | integer | 0..1 | Dynamic load information. |
| recoveryTime | DateTime | 0..1 | Timestamp when the NF service was (re)started. |
| chfServiceInfo | ChfServiceInfo | 0..1 | Specific data for a CHF service instance. |
| supportedFeatures | SupportedFeatures | 0..1 | Supported Features of the NF Service instance. |

NOTE 1: The NF Service Consumer will construct the API URIs of the service using the FQDN and IP address related attributes.
NOTE 2: The capacity and priority parameters, if present, are used for NF selection and load balancing.
NOTE 3: The NRF shall notify NFs subscribed to receiving notifications of changes of the NF profile, if the recoveryTime or the nfServiceStatus is changed.
NOTE 4: A requester NF subscribed to NF status changes may consider that all the resources created in the NF service before the NF service recovery time have been lost.
NOTE 5: If this attribute is present in the NFService and in the NF profile, the attribute from the NFService shall prevail.
NOTE 6: Other NFs are in a different PLMN if they belong to none of the PLMN ID(s) configured for the PLMN of the NRF.

##### 6.1.6.2.4 Type: DefaultNotificationSubscription

### Table 6.1.6.2.4-1: Definition of type DefaultNotificationSubscription
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| notificationType | NotificationType | 1 | Type of notification for which the corresponding callback URI is provided. |
| callbackUri | Uri | 1 | The callback URI. |
| n1MessageClass | N1MessageClass | 0..1 | If the notification type is N1_MESSAGES, this IE shall identify the class of N1 messages to be notified. |
| n2InformationClass | N2InformationClass | 0..1 | If the notification type is N2_INFORMATION, this IE shall identify the class of N2 information to be notified. |

##### 6.1.6.2.5 Type: IpEndPoint

### Table 6.1.6.2.5-1: Definition of type IpEndPoint
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| ipv4Address | Ipv4Addr | 0..1 | IPv4 address. |
| ipv6Address | Ipv6Addr | 0..1 | IPv6 address. |
| transport | TransportProtocol | 0..1 | Transport protocol. |
| port | integer | 0..1 | Port number. |

NOTE 1: At most one occurrence of either ipv4Address or ipv6Address shall be included in this data structure.
NOTE 2: If the port number is absent from the ipEndPoints attribute, the NF service consumer shall use the default HTTP port number, i.e. TCP port 80 for "http" URIs or TCP port 443 for "https" URIs as specified in IETF RFC 7540 [9] when invoking the service.

##### 6.1.6.2.6 Type: UdrInfo

### Table 6.1.6.2.6-1: Definition of type UdrInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| groupId | NfGroupId | 0..1 | Identity of the UDR group that is served by the UDR instance. If not provided, the UDR instance does not pertain to any UDR group. |
| supiRanges | array(SupiRange) | 1..N | List of ranges of SUPIs whose profile data is available in the UDR instance. |
| gpsiRanges | array(IdentityRange) | 1..N | List of ranges of GPSIs whose profile data is available in the UDR instance. |
| externalGroupIdentifiersRanges | array(IdentityRange) | 1..N | List of ranges of external groups whose profile data is available in the UDR instance. |
| supportedDataSets | array(DataSetId) | 1..N | List of supported data sets in the UDR instance. If not provided, the UDR supports all data sets. |

NOTE 1: If none of these parameters is provided, the UDR can serve any external group and any SUPI or GPSI.

##### 6.1.6.2.7 Type: UdmInfo

### Table 6.1.6.2.7-1: Definition of type UdmInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| groupId | NfGroupId | 0..1 | Identity of the UDM group that is served by the UDM instance. If not provided, the UDM instance does not pertain to any UDM group. |
| supiRanges | array(SupiRange) | 1..N | List of ranges of SUPIs whose profile data is available in the UDM instance. |
| gpsiRanges | array(IdentityRange) | 1..N | List of ranges of GPSIs whose profile data is available in the UDM instance. |
| externalGroupIdentifiersRanges | array(IdentityRange) | 1..N | List of ranges of external groups whose profile data is available in the UDM instance. |
| routingIndicators | array(string) | 1..N | List of Routing Indicator information that allows network signalling with SUCI to route to the UDM instance. Pattern: `^[0-9]{1,4}$` |

NOTE 1: If none of these parameters is provided, the UDM can serve any external group and any SUPI or GPSI.

##### 6.1.6.2.8 Type: AusfInfo

### Table 6.1.6.2.8-1: Definition of type AusfInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| groupId | NfGroupId | 0..1 | Identity of the AUSF group. If not provided, the AUSF instance does not pertain to any AUSF group. |
| supiRanges | array(SupiRange) | 1..N | List of ranges of SUPIs that can be served by the AUSF instance. If not provided, the AUSF can serve any SUPI. |
| routingIndicators | array(string) | 1..N | List of Routing Indicator information that allows network signalling with SUCI to route to the AUSF instance. Pattern: `^[0-9]{1,4}$` |

##### 6.1.6.2.9 Type: SupiRange

### Table 6.1.6.2.9-1: Definition of type SupiRange
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| start | string | 0..1 | First value identifying the start of a SUPI range. Pattern: `^[0-9]+$` |
| end | string | 0..1 | Last value identifying the end of a SUPI range. Pattern: `^[0-9]+$` |
| pattern | string | 0..1 | Pattern representing the set of SUPIs belonging to this range. |

NOTE: Either the start and end attributes, or the pattern attribute, shall be present.

EXAMPLE 1: IMSI range. From: 123 45 6789040000 To: 123 45 6789059999 (i.e., 20,000 IMSI numbers) JSON: { "start": "123456789040000", "end": "123456789059999" }

EXAMPLE 2: IMSI range. From: 123 45 6789040000 To: 123 45 6789049999 (i.e., 10,000 IMSI numbers) JSON: { "pattern": "^imsi-12345678904[0-9]{4}$" }, or JSON: { "start": "123456789040000", "end": "123456789049999" }

EXAMPLE 3: NAI range. "smartmeter-{factoryID}@company.com" where "{factoryID}" can be any string. JSON: { "pattern": "^nai-smartmeter-.+@company\.com$" }

##### 6.1.6.2.10 Type: IdentityRange

### Table 6.1.6.2.10-1: Definition of type IdentityRange
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| start | string | 0..1 | First value identifying the start of an identity range. Pattern: `^[0-9]+$` |
| end | string | 0..1 | Last value identifying the end of an identity range. Pattern: `^[0-9]+$` |
| pattern | string | 0..1 | Pattern representing the set of identities belonging to this range. |

NOTE: Either the start and end attributes, or the pattern attribute, shall be present.

##### 6.1.6.2.11 Type: AmfInfo

### Table 6.1.6.2.11-1: Definition of type AmfInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| amfRegionId | AmfRegionId | 1 | AMF region identifier. |
| amfSetId | AmfSetId | 1 | AMF set identifier. |
| guamiList | array(Guami) | 1..N | List of supported GUAMIs. |
| taiList | array(Tai) | 1..N | List of TAIs the AMF can serve. |
| taiRangeList | array(TaiRange) | 1..N | Range of TAIs the AMF can serve. |
| backupInfoAmfFailure | array(Guami) | 1..N | List of GUAMIs for which the AMF acts as a backup for AMF failure. |
| backupInfoAmfRemoval | array(Guami) | 1..N | List of GUAMIs for which the AMF acts as a backup for planned AMF removal. |
| n2InterfaceAmfInfo | N2InterfaceAmfInfo | 0..1 | N2 interface information of the AMF. |

##### 6.1.6.2.12 Type: SmfInfo

### Table 6.1.6.2.12-1: Definition of type SmfInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| sNssaiSmfInfoList | array(sNssaiSmfInfoItem) | 1..N | List of parameters supported by the SMF per S-NSSAI. |
| taiList | array(Tai) | 1..N | The list of TAIs the SMF can serve. |
| taiRangeList | array(TaiRange) | 1..N | The range of TAIs the SMF can serve. |
| pgwFqdn | Fqdn | 0..1 | The FQDN of the PGW if the SMF is a combined SMF/PGW-C. |
| accessType | array(AccessType) | 1..2 | Access type(s) supported by the SMF. |

##### 6.1.6.2.13 Type: UpfInfo

### Table 6.1.6.2.13-1: Definition of type UpfInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| sNssaiUpfInfoList | array(SnssaiUpfInfoItem) | 1..N | List of parameters supported by the UPF per S-NSSAI. |
| smfServingArea | array(string) | 1..N | The SMF service area(s) the UPF can serve. |
| interfaceUpfInfoList | array(InterfaceUpfInfoItem) | 1..N | List of User Plane interfaces configured on the UPF. |
| iwkEpsInd | boolean | 0..1 | Indicates whether interworking with EPS is supported by the UPF. |
| pduSessionTypes | array(PduSessionType) | 1..N | List of PDU session type(s) supported by the UPF. |

##### 6.1.6.2.14 Type: SnssaiUpfInfoItem

### Table 6.1.6.2.14-1: Definition of type SnssaiUpfInfoItem
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| sNssai | Snssai | 1 | Supported S-NSSAI. |
| dnnUpfInfoList | array(DnnUpfInfoItem) | 1..N | List of parameters supported by the UPF per DNN. |

##### 6.1.6.2.15 Type: DnnUpfInfoItem

### Table 6.1.6.2.15-1: Definition of type DnnUpfInfoItem
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| dnn | Dnn | 1 | Supported DNN. |
| dnaiList | array(Dnai) | 1..N | List of Data network access identifiers supported by the UPF for this DNN. |
| pduSessionTypes | array(PduSessionType) | 1..N | List of PDU session type(s) supported by the UPF for a specific DNN. |

##### 6.1.6.2.16 Type: SubscriptionData

### Table 6.1.6.2.16-1: Definition of type SubscriptionData
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| nfStatusNotificationUri | Uri | 1 | Callback URI where the NF Service Consumer will receive the notifications from NRF. |
| subscrCond | SubscrCond | 0..1 | Conditions identifying the set of NF Instances whose status is requested to be monitored. If absent, the NF Service Consumer requests a subscription to all NFs in the NRF. |
| subscriptionId | string | 0..1 | Subscription ID for the newly created resource. Read-only. |
| validityTime | DateTime | 0..1 | Time instant after which the subscription becomes invalid. |
| reqNotifEvents | array(NotificationEventType) | 1..N | List of event types that the NF Service Consumer is interested in receiving. If absent, notifications for all event types are requested. |
| reqNfType | NFType | 0..1 | NF type of the NF Service Consumer requesting the subscription. |
| reqNfFqdn | Fqdn | 0..1 | FQDN of the NF Service Consumer requesting the subscription. |
| plmnId | PlmnId | 0..1 | Target PLMN ID of the NF Instance(s) whose status is requested to be monitored. |
| notifCondition | NotifCondition | 0..1 | Conditions that trigger a notification from NRF. |

NOTE: The "subscription to all NFs" may be quite demanding in terms of resources in NRF and also in terms of network traffic of the resulting notifications, so it should be authorized by NRF under very strict policies (e.g. only to a specific requesting NF, as indicated by reqNfType and reqNfFqdn attributes).

##### 6.1.6.2.17 Type: NotificationData

### Table 6.1.6.2.17-1: Definition of type NotificationData
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| event | NotificationEventType | 1 | Notification type. It shall take the values `NF_REGISTERED`, `NF_DEREGISTERED` or `NF_PROFILE_CHANGED`. |
| nfInstanceUri | Uri | 1 | URI of the NF Instance associated to the notification event. |
| nfProfile | NFProfile | 0..1 | New NF Profile or Updated NF Profile. |
| profileChanges | array(ChangeItem) | 1..N | List of changes on the profile of the NF Instance associated to the notification event. |

NOTE 1: If `event` takes the value `NF_PROFILE_CHANGED`, then either `nfProfile` or `profileChanges` attributes shall be present, but not both.

EXAMPLE: Notification payload sent from NRF when an NF Instance has changed its profile by updating the value of the `recoveryTime` attribute of its NF Profile, and updated the TCP port of the first NF Service Instance: { "event": "NF_PROFILE_CHANGED", "nfInstanceUri": ".../nf-instances/4947a69a-f61b-4bc1-b9da-47c9c5d14b64", "profileChanges": [ { "op": "REPLACE", "path": "/recoveryTime", "newValue": "2018-12-30T23:20:50Z" }, { "op": "REPLACE", "path": "/nfServices/0/ipEndPoints/0/port", "newValue": 8080 } ] }

##### 6.1.6.2.18 Void

##### 6.1.6.2.19 Type: NFServiceVersion

### Table 6.1.6.2.19-1: Definition of type NFServiceVersion
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| apiVersionInUri | string | 1 | Version of the service instance to be used in the URI for accessing the API (e.g. `v1`). |
| apiFullVersion | string | 1 | Full version number of the API as specified in subclause 4.3.1 of 3GPP TS 29.501 [5]. |
| expiry | DateTime | 0..1 | Expiry date and time of the NF service. |

##### 6.1.6.2.20 Type: PcfInfo

### Table 6.1.6.2.20-1: Definition of type PcfInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| dnnList | array(Dnn) | 1..N | DNNs supported by the PCF. |
| supiRanges | array(SupiRange) | 1..N | List of ranges of SUPIs that can be served by the PCF instance. |
| rxDiamHost | DiameterIdentity | 0..1 | Diameter host of the Rx interface for the PCF. |
| rxDiamRealm | DiameterIdentity | 0..1 | Diameter realm of the Rx interface for the PCF. |

##### 6.1.6.2.21 Type: BsfInfo

### Table 6.1.6.2.21-1: Definition of type BsfInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| ipv4AddressRanges | array(Ipv4AddressRange) | 1..N | List of ranges of IPv4 addresses handled by BSF. |
| dnnList | array(Dnn) | 1..N | List of DNNs handled by the BSF. |
| ipDomainList | array(string) | 1..N | List of IPv4 address domains handled by the BSF. |
| ipv6PrefixRanges | array(Ipv6PrefixRange) | 1..N | List of ranges of IPv6 prefixes handled by the BSF. |

##### 6.1.6.2.22 Type: Ipv4AddressRange

### Table 6.1.6.2.22-1: Definition of type IPv4AddressRange
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| start | Ipv4Addr | 1 | First value identifying the start of an IPv4 address range. |
| end | Ipv4Addr | 1 | Last value identifying the end of an IPv4 address range. |

##### 6.1.6.2.23 Type: Ipv6PrefixRange

### Table 6.1.6.2.23-1: Definition of type IPv6PrefixRange
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| start | Ipv6Prefix | 1 | First value identifying the start of an IPv6 prefix range. |
| end | Ipv6Prefix | 1 | Last value identifying the end of an IPv6 prefix range. |

##### 6.1.6.2.24 Type: InterfaceUpfInfoItem

### Table 6.1.6.2.24-1: Definition of type InterfaceUpfInfoItem
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| interfaceType | UPInterfaceType | 1 | User Plane interface type. |
| ipv4EndpointAddresses | array(Ipv4Addr) | 1..N | Available endpoint IPv4 address(es) of the User Plane interface. |
| ipv6EndpointAddresses | array(Ipv6Addr) | 1..N | Available endpoint IPv6 address(es) of the User Plane interface. |
| endpointFqdn | Fqdn | 0..1 | FQDN of available endpoint of the User Plane interface. |
| networkInstance | string | 0..1 | Network Instance associated to the User Plane interface. |

NOTE 1: At least one of the addressing parameters (ipv4address, ipv6adress or endpointFqdn) shall be included in the InterfaceUpfInfoItem.

##### 6.1.6.2.25 Type: UriList

### Table 6.1.6.2.25-1: Definition of type UriList
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| _links | map(LinksValueSchema) | 1..N | See sub-clause 4.9.4 of 3GPP TS 29.501 [5] for the description of the members. |

##### 6.1.6.2.26 Type: N2InterfaceAmfInfo

### Table 6.1.6.2.26-1: Definition of type N2InterfaceAmfInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| ipv4EndpointAddress | array(Ipv4Addr) | 1..N | Available AMF endpoint IPv4 address(es) for N2. |
| ipv6EndpointAddress | array(Ipv6Addr) | 1..N | Available AMF endpoint IPv6 address(es) for N2. |
| amfName | AmfName | 0..1 | AMF Name. |

NOTE 1: At least one of the addressing parameters (ipv4address or ipv6adress) shall be included.

##### 6.1.6.2.27 Type: TaiRange

### Table 6.1.6.2.27-1: Definition of type TaiRange
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| plmnId | PlmnId | 1 | PLMN ID related to the TacRange. |
| tacRangeList | array(TacRange) | 1..N | The range of the TACs. |

##### 6.1.6.2.28 Type: TacRange

### Table 6.1.6.2.28-1: Definition of type TacRange
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| start | string | 0..1 | First value identifying the start of a TAC range. Pattern: `^([A-Fa-f0-9]{4}|[A-Fa-f0-9]{6})$` |
| end | string | 0..1 | Last value identifying the end of a TAC range. Pattern: `^([A-Fa-f0-9]{4}|[A-Fa-f0-9]{6})$` |
| pattern | string | 0..1 | Pattern representing the set of TACs belonging to this range. |

NOTE: Either the start and end attributes, or the pattern attribute, shall be present.

EXAMPLE 1: TAC range. From: 543000 To: 5433E7 (i.e., 1000 TAC numbers) JSON: { "start": "543000", "end": "5433E7" }

EXAMPLE 2: TAC range. From: 54E000 To: 54EFFF (i.e., 4096 TAC numbers) JSON: { "pattern": "^54E[0-9a-fA-F]{3}$" }, or JSON: { "start": "54E000", "end": "54EFFF" }

##### 6.1.6.2.29 Type: SnssaiSmfInfoItem

### Table 6.1.6.2.29-1: Definition of type SnssaiSmfInfoItem
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| sNssai | Snssai | 1 | Supported S-NSSAI. |
| dnnSmfInfoList | array(DnnSmfInfoItem) | 1..N | List of parameters supported by the SMF per DNN. |

##### 6.1.6.2.30 Type: DnnSmfInfoItem

### Table 6.1.6.2.30-1: Definition of type DnnSmfInfoItem
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| dnn | Dnn | 1 | Supported DNN. |

##### 6.1.6.2.31 Type: NrfInfo

### Table 6.1.6.2.31-1: Definition of type NrfInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| servedUdrInfo | map(UdrInfo) | 1..N | Contains UdrInfo attributes configured in the NRF or received during NF registration. |
| servedUdmInfo | map(UdmInfo) | 1..N | Contains UdmInfo attributes configured in the NRF or received during NF registration. |
| servedAusfInfo | map(AusfInfo) | 1..N | Contains AusfInfo attributes configured in the NRF or received during NF registration. |
| servedAmfInfo | map(AmfInfo) | 1..N | Contains AmfInfo attributes configured in the NRF or received during NF registration. |
| servedSmfInfo | map(SmfInfo) | 1..N | Contains SmfInfo attributes configured in the NRF or received during NF registration. |
| servedUpfInfo | map(UpfInfo) | 1..N | Contains UpfInfo attributes configured in the NRF or received during NF registration. |
| servedPcfInfo | map(PcfInfo) | 1..N | Contains PcfInfo attributes configured in the NRF or received during NF registration. |
| servedBsfInfo | map(BsfInfo) | 1..N | Contains BsfInfo attributes configured in the NRF or received during NF registration. |
| servedChfInfo | Map(ChfInfo) | 1..N | Contains ChfInfo attributes configured in the NRF or received during NF registration. |

NOTE: The absence of these parameters means the NRF is able to serve any NF discovery request.

##### 6.1.6.2.32 Type: ChfInfo

### Table 6.1.6.2.32-1: Definition of type ChfInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| supiRangeList | array(SupiRange) | 1..N | List of ranges of SUPIs that can be served by the CHF instance. |
| gpsiRangeList | array(IdentityRange) | 1..N | List of ranges of GPSIs that can be served by the CHF instance. |
| plmnRangeList | array(PlmnRange) | 1..N | List of ranges of PLMNs that can be served by the CHF instance. |

##### 6.1.6.2.33 Type: ChfServiceInfo

### Table 6.1.6.2.33-1: Definition of type ChfServiceInfo
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| primaryChfServiceInstance | string | 0..1 | Present if the CHF service instance serves as a secondary CHF instance of another primary CHF service instance. |
| secondaryChfServiceInstance | string | 0..1 | Present if the CHF service instance serves as a primary CHF instance of another secondary CHF service instance. |

##### 6.1.6.2.34 Type: PlmnRange

### Table 6.1.6.2.34-1: Definition of type PlmnRange
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| start | string | 0..1 | First value identifying the start of a PLMN range. The string shall be encoded as `<MCC><MNC>`. Pattern: `^[0-9]{3}[0-9]{2,3}$` |
| end | string | 0..1 | Last value identifying the end of a PLMN range. The string shall be encoded as `<MCC><MNC>`. Pattern: `^[0-9]{3}[0-9]{2,3}$` |
| pattern | string | 0..1 | Pattern representing the set of PLMNs belonging to this range. |

NOTE: Either the start and end attributes, or the pattern attribute, shall be present.

EXAMPLE 1: PLMN range. MCC 123, any MNC JSON: { "start": "12300", "end": "123999" }

EXAMPLE 2: PLMN range. MCC 123, MNC within range 45 to 49 JSON: { "pattern": "^1234[5-9]$" }, or JSON: { "start": "12345", "end": "12349" }

EXAMPLE 3: PLMN range. MCC within range 123 to 257, any MNC JSON: { "start": "12300", "end": "257999" }

##### 6.1.6.2.35 Type: SubscrCond

### Table 6.1.6.2.35-1: Definition of type SubscrCond as a list of mutually exclusive alternatives
| Data type | Cardinality | Description |
| --- | --- | --- |
| NfInstanceIdCond | 1 | Subscription to a given NF Instance. |
| NfTypeCond | 1 | Subscription to a set of NF Instances, identified by their NF Type. |
| ServiceNameCond | 1 | Subscription to a set of NF Instances that offer a certain service name. |
| AmfCond | 1 | Subscription to a set of NF Instances (AMFs), belonging to a certain AMF Set and/or AMF Region. |
| GuamiListCond | 1 | Subscription to a set of NF Instances (AMFs), identified by their Guamis. |
| NetworkSliceCond | 1 | Subscription to a set of NF Instances, identified by S-NSSAI(s) and NSI ID(s). |
| NfGroupCond | 1 | Subscription to a set of NF Instances, identified by a NF (UDM, AUSF or UDR) Group Identity. |

##### 6.1.6.2.36 Type: NfInstanceCond

### Table 6.1.6.2.36-1: Definition of type NfInstanceCond
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| nfInstanceId | NfInstanceId | 1 | NF Instance ID of the NF Instance whose status is requested to be monitored. |

##### 6.1.6.2.37 Type: NfTypeCond

### Table 6.1.6.2.37-1: Definition of type NfTypeCond
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| nfType | NFType | 1 | NF type of the NF Instances whose status is requested to be monitored. |

##### 6.1.6.2.38 Type: ServiceNameCond

### Table 6.1.6.2.38-1: Definition of type ServiceNameCond
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| serviceName | ServiceName | 1 | Service name offered by the NF Instances whose status is requested to be monitored. |

##### 6.1.6.2.39 Type: AmfCond

### Table 6.1.6.2.39-1: Definition of type AmfCond
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| amfSetId | AmfSetId | 1 | AMF Set ID of the NF Instances (AMF) whose status is requested to be monitored. |
| amfRegionId | AmfRegionId | 1 | AMF Region ID of the NF Instances (AMF) whose status is requested to be monitored. |

NOTE 1: At least amfSetId or amfRegionId shall be present.
NOTE 2: The PLMN ID of the AMF Region and AMF Set may be indicated in the plmnId attribute in the SubscriptionData.

##### 6.1.6.2.40 Type: GuamiListCond

### Table 6.1.6.2.40-1: Definition of type GuamiListCond
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| guamiList | array(Guami) | 1..N | Guamis of the NF Instances (AMFs) whose status is requested to be monitored. |

##### 6.1.6.2.41 Type: NetworkSliceCond

### Table 6.1.6.2.41-1: Definition of type NetworkSliceCond
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| snssaiList | array(Snssai) | 1..N | S-NSSAIs of the NF Instances whose status is requested to be monitored. |
| nsiList | array(string) | 1..N | NSI IDs of the NF Instances whose status is requested to be monitored. |

##### 6.1.6.2.42 Type: NfGroupCond

### Table 6.1.6.2.42-1: Definition of type NfGroupCond
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| nfType | string | 1 | NF type (UDM, AUSF or UDR) of the NF Instances whose status is requested to be monitored. |
| nfGroupId | NfGroupId | 1 | Group ID of the NF Instances whose status is requested to be monitored. |

##### 6.1.6.2.43 Type: NotifCondition

### Table 6.1.6.2.43-1: Definition of type NotifCondition
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| monitoredAttributes | array(string) | 1..N | List of JSON Pointers of attributes in the NF Profile. If present, the NRF shall send notification only for changes in the attributes included in this list. |
| unmonitoredAttributes | array(string) | 1..N | List of JSON Pointers of attributes in the NF Profile. If present, the NRF shall send notification for changes on any attribute except those included in this list. |

NOTE 1: Attributes `monitoredAttributes` and `unmonitoredAttributes` shall not be included simultaneously.

EXAMPLE 1: The following JSON object would represent a monitoring condition where the client requests to be notified of all changes on the NF Profile, except `load` attribute. { "unmonitoredAttributes": [ "/load" ] }

EXAMPLE 2: The following JSON object would represent a monitoring condition where the client requests to be notified only of changes on attribute `nfStatus`: { "monitoredAttributes": [ "/nfStatus" ] }

##### 6.1.6.2.44 Type: PlmnSnssai

### Table 6.1.6.2.44-1: Definition of type PlmnSnssai
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| plmnId | PlmnId | 1 | PLMN ID for which list of supported S-NSSAI(s) is provided. |
| sNssaiList | array(Snssai) | 1..N | The specific list of S-NSSAIs supported by the given PLMN. |

#### 6.1.6.3 Simple data types and enumerations

##### 6.1.6.3.1 Introduction

This subclause defines simple data types and enumerations that can be referenced from data structures defined in the previous subclauses.

##### 6.1.6.3.2 Simple data types

The simple data types defined in table 6.1.6.3.2-1 shall be supported.

### Table 6.1.6.3.2-1: Simple data types
| Type Name | Type Definition | Description |
| --- | --- | --- |
| Fqdn | string | FQDN (Fully Qualified Domain Name) |

##### 6.1.6.3.3 Enumeration: NFType

The enumeration NFType represents the different types of Network Functions that can be found in the 5GC.

### Table 6.1.6.3.3-1: Enumeration NFType
| Enumeration value | Description |
| --- | --- |
| NRF | Network Function: NRF |
| UDM | Network Function: UDM |
| AMF | Network Function: AMF |
| SMF | Network Function: SMF |
| AUSF | Network Function: AUSF |
| NEF | Network Function: NEF |
| PCF | Network Function: PCF |
| SMSF | Network Function: SMSF |
| NSSF | Network Function: NSSF |
| UDR | Network Function: UDR |
| LMF | Network Function: LMF |
| GMLC | Network Function: GMLC |
| 5G_EIR | Network Function: 5G-EIR |
| SEPP | Network Function: SEPP |
| UPF | Network Function: UPF |
| N3IWF | Network Function: N3IWF |
| AF | Network Function: AF |
| UDSF | Network Function: UDSF |
| BSF | Network Function: BSF |
| CHF | Network Function: CHF |
| NWDAF | Network Function: NWDAF |

##### 6.1.6.3.4 Enumeration: NotificationType

### Table 6.1.6.3.4-1: Enumeration NotificationType
| Enumeration value | Description |
| --- | --- |
| N1_MESSAGES | Notification of N1 messages |
| N2_INFORMATION | Notification of N2 information |
| LOCATION_NOTIFICATION | Notification of Location Information by AMF towards NF Service Consumers (e.g. GMLC) |
| DATA_REMOVAL_NOTIFICATION | Notification of Data Removal by UDR (e.g. removal of UE registration data upon subscription withdrawal) |
| DATA_CHANGE_NOTIFICATION | Notification of Data Changes by UDR |

##### 6.1.6.3.5 Enumeration: TransportProtocol

### Table 6.1.6.3.5-1: Enumeration TransportProtocol
| Enumeration value | Description |
| --- | --- |
| TCP | Transport protocol: TCP |

##### 6.1.6.3.6 Enumeration: NotificationEventType

### Table 6.1.6.3.6-1: Enumeration NotificationEventType
| Enumeration value | Description |
| --- | --- |
| NF_REGISTERED | The NF Instance has been registered in NRF |
| NF_DEREGISTERED | The NF Instance has been deregistered from NRF |
| NF_PROFILE_CHANGED | The profile of the NF Instance has been modified |

##### 6.1.6.3.7 Enumeration: NFStatus

### Table 6.1.6.3.7-1: Enumeration NFStatus
| Enumeration value | Description |
| --- | --- |
| REGISTERED | The NF Instance is registered in NRF and can be discovered by other NFs. |
| SUSPENDED | The NF Instance is registered in NRF but it is not operative and cannot be discovered by other NFs. |
| UNDISCOVERABLE | The NF instance is registered in NRF, is operative but cannot be discovered by other NFs. |

##### 6.1.6.3.8 Enumeration: DataSetId

The enumeration DataSetId represents the different types of data sets supported by an UDR instance.

### Table 6.1.6.3.8-1: Enumeration DataSetId
| Enumeration value | Description |
| --- | --- |
| SUBSCRIPTION | Data set: Subscription data |
| POLICY | Data set: Policy data |
| EXPOSURE | Data set: Structured data for exposure |
| APPLICATION | Data set: Application data |

##### 6.1.6.3.9 Enumeration: UPInterfaceType

### Table 6.1.6.3.9-1: Enumeration UPInterfaceType
| Enumeration value | Description |
| --- | --- |
| N3 | User Plane Interface: N3 |
| N6 | User Plane Interface: N6 |
| N9 | User Plane Interface: N9 |

##### 6.1.6.3.10 Relation Types

###### 6.1.6.3.10.1 General

This clause describes the possible relation types defined within NRF API. See sub-clause 4.7.5.2 of 3GPP TS 29.501 [5] for the description of the relation types.

### Table 6.1.6.3.10.1-1: supported registered relation types
| Relation Name | Description |
| --- | --- |
| self | self |
| item | item |

##### 6.1.6.3.11 Enumeration: ServiceName

### Table 6.1.6.3.11-1: Enumeration ServiceName
| Enumeration value | Description |
| --- | --- |
| nnrf-nfm | Nnrf_NFManagement Service offered by the NRF |
| nnrf-disc | Nnrf_NFDiscovery Service offered by the NRF |
| nudm-sdm | Nudm_SubscriberDataManagement Service offered by the UDM |
| nudm-uecm | Nudm_UEContextManagement Service offered by the UDM |
| nudm-ueau | Nudm_UEAuthentication Service offered by the UDM |
| nudm-ee | Nudm_EventExposure Service offered by the UDM |
| nudm-pp | Nudm_ParameterProvision Service offered by the UDM |
| namf-comm | Namf_Communication Service offered by the AMF |
| namf-evts | Namf_EventExposure Service offered by the AMF |
| namf-mt | Namf_MT Service offered by the AMF |
| namf-loc | Namf_Location Service offered by the AMF |
| nsmf-pdusession | Nsmf_PDUSession Service offered by the SMF |
| nsmf-event-exposure | Nsmf_EventExposure Service offered by the SMF |
| nausf-auth | Nausf_UEAuthentication Service offered by the AUSF |
| nausf-sorprotection | Nausf_SoRProtection Service offered by the AUSF |
| nausf-upuprotection | Nausf_UPUProtection Service offered by the AUSF |
| nnef-pfdmanagement | Nnef_PFDManagement offered by the NEF |
| npcf-am-policy-control | Npcf_AMPolicyControl Service offered by the PCF |
| npcf-smpolicycontrol | Npcf_SMPolicyControl Service offered by the PCF |
| npcf-policyauthorization | Npcf_PolicyAuthorization Service offered by the PCF |
| npcf-bdtpolicycontrol | Npcf_BDTPolicyControl Service offered by the PCF |
| npcf-eventexposure | Npcf_EventExposure Service offered by the PCF |
| npcf-ue-policy-control | Npcf_UEPolicyControl Service offered by the PCF |
| nsmsf-sms | Nsmsf_SMService Service offered by the SMSF |
| nnssf-nsselection | Nnssf_NSSelection Service offered by the NSSF |
| nnssf-nssaiavailability | Nnssf_NSSAIAvailability Service offered by the NSSF |
| nudr-dr | Nudr_DataRepository Service offered by the UDR |
| nlmf-loc | Nlmf_Location Service offered by the LMF |
| n5g-eir-eic | N5g-eir_EquipmentIdentityCheck Service offered by the 5G-EIR |
| nbsf-management | Nbsf_Management Service offered by the BSF |
| nchf-spendinglimitcontrol | Nchf_SpendingLimitControl Service offered by the CHF |
| nchf-convergedcharging | Nchf_Converged_Charging Service offered by the CHF |
| nnwdaf-eventssubscription | Nnwdaf_EventsSubscription Service offered by the NWDAF |
| nnwdaf-analyticsinfo | Nnwdaf_AnalyticsInfo Service offered by the NWDAF |

NOTE: The services defined in this table are those defined by 3GPP NFs in 5GC; however, in order to support custom services offered by standard and custom NFs, the NRF shall also accept the registration of NF Services with other service names.

##### 6.1.6.3.12 Enumeration: NFServiceStatus

### Table 6.1.6.3.12-1: Enumeration NFServiceStatus
| Enumeration value | Description |
| --- | --- |
| REGISTERED | The NF Service Instance is registered in NRF and can be discovered by other NFs. |
| SUSPENDED | The NF Service Instance is registered in NRF but it is not operative and cannot be discovered by other NFs. |
| UNDISCOVERABLE | The NF Service instance is registered in NRF, is operative but cannot be discovered by other NFs. |

### 6.1.7 Error Handling

#### 6.1.7.1 General

HTTP error handling shall be supported as specified in subclause 5.2.4 of 3GPP TS 29.500 [4].

#### 6.1.7.2 Protocol Errors

Protocol errors handling shall be supported as specified in subclause 5.2.7 of 3GPP TS 29.500 [4].

#### 6.1.7.3 Application Errors

The application errors defined for the Nnrf_NFManagement service are listed in Table 6.1.7.3-1.

### Table 6.1.7.3-1: Application errors

Application Error HTTP status code Description

### 6.1.8 Security

As indicated in 3GPP TS 33.501 [15], the access to the Nnrf_NFManagement API may be authorized by means of the OAuth2 protocol (see IETF RFC 6749 [16]), using the "Client Credentials" authorization grant, where the NRF plays the role of the authorization server.

If Oauth2 authorization is used, an NF Service Consumer, prior to consuming services offered by the Nnrf_NFManagement API, shall obtain a "token" from the authorization server, by invoking the Access Token Request service, as described in subclause 5.4.2.2.

NOTE: When multiple NRFs are deployed in a network, the NRF used as authorization server is the same NRF where the Nnrf_NFManagement service is invoked by the NF Service Producer.

The Nnrf_NFManagement API defines scopes for OAuth2 authorization as specified in 3GPP TS 33.501 [15]; it defines a single scope consisting on the name of the service (i.e., "nnrf-nfm"), and it does not define any additional scopes at resource or operation level.

## 6.2 Nnrf_NFDiscovery Service API

### 6.2.1 API URI

URIs of this API shall have the following root:

{apiRoot}/{apiName}/{apiVersion}/

where "apiRoot" is defined in subclause 4.4.1 of 3GPP TS 29.501 [5], the "apiName" shall be set to "nnrf-disc" and the "apiVersion" shall be set to "v1" for the current version of this specification.

### 6.2.2 Usage of HTTP

#### 6.2.2.1 General

HTTP/2, as defined in IETF RFC 7540 [9], shall be used as specified in clause 5 of 3GPP TS 29.500 [4].

HTTP/2 shall be transported as specified in subclause 5.3 of 3GPP TS 29.500 [4].

HTTP messages and bodies for the Nnrf_NFDiscovery service shall comply with the OpenAPI [10] specification contained in Annex A.

#### 6.2.2.2 HTTP Standard Headers

##### 6.2.2.2.1 General

The mandatory standard HTTP headers as specified in subclause 5.2.2.2 of 3GPP TS 29.500 [4] shall be supported.

##### 6.2.2.2.2 Content type

The following content types shall be supported:

- The JSON format (IETF RFC 8259 [22]). The use of the JSON format shall be signalled by the content type "application/json". See also subclause 5.4 of 3GPP TS 29.500 [4].

- The Problem Details JSON Object (IETF RFC 7807 [11]). The use of the Problem Details JSON object in a HTTP response body shall be signalled by the content type "application/problem+json".

##### 6.2.2.2.3 Cache-Control

A "Cache-Control" header should be included in HTTP responses, as described in IETF RFC 7234 [20], section 5.2. It shall contain a "max-age" value, indicating the amount of time in seconds after which the received response is considered stale; this value shall be the same as the content of the "validityPeriod" element described in subclause 6.2.6.2.2.

##### 6.2.2.2.4 ETag

An "ETag" (entity-tag) header should be included in HTTP responses, as described in IETF RFC 7232 [19], section 2.3. It shall contain a server-generated strong validator, that allows further matching of this value (included in subsequent client requests) with a given resource representation stored in the server or in a cache.

##### 6.2.2.2.5 If-None-Match

An NF Service Consumer should issue conditional GET request towards NRF, by including an If-None-Match header in HTTP requests, as described in IETF RFC 7232 [19], section 3.2, containing one or several entity tags received in previous responses for the same resource.

#### 6.2.2.3 HTTP custom headers

##### 6.2.2.3.1 General

In this release of this specification, no custom headers specific to the Nnrf_NFDiscovery service are defined. For 3GPP specific HTTP custom headers used across all service-based interfaces, see subclause 5.2.3 of 3GPP TS 29.500 [4].

### 6.2.3 Resources

#### 6.2.3.1 Overview

The structure of the Resource URIs of the NFDiscovery service is shown in figure 6.2.3.1-1.

{apiRoot}/nnrf-disc/v1

/nf-instances

Figure 6.2.3.1-1: Resource URI structure of the NFDiscovery API

### Table 6.2.3.1-1 provides an overview of the resources and applicable HTTP methods.

### Table 6.2.3.1-1: Resources and methods overview
| Resource name | Resource URI | HTTP method or custom operation | Description |
| --- | --- | --- | --- |
| nf-instances (Store) | {apiRoot}/nnrf-disc/v1/nf-instances | GET | Retrieve a collection of NF Instances according to certain filter criteria. |

#### 6.2.3.2 Resource: nf-instances (Store)

##### 6.2.3.2.1 Description

This resource represents a collection of the different NF instances registered in the NRF.

This resource is modelled as the Store resource archetype (see subclause C.3 of 3GPP TS 29.501 [5]).

##### 6.2.3.2.2 Resource Definition

Resource URI: {apiRoot}/nnrf-disc/v1/nf-instances

This resource shall support the resource URI variables defined in table 6.2.3.2.2-1.

### Table 6.2.3.2.2-1: Resource URI variables for this resource
| Name | Description |
| --- | --- |
| apiRoot | See subclause 6.1.1 |

##### 6.2.3.2.3 Resource Standard Methods

###### 6.2.3.2.3.1 GET

This operation retrieves a list of NF Instances, and their offered services, currently registered in the NRF, satisfying a number of filter criteria, such as those NF Instances offering a certain service name, or those NF Instances of a given NF type (e.g., AMF).

### Table 6.2.3.2.3.1-1: URI query parameters supported by the GET method on this resource
| Name | Data type | Cardinality | Description | Applicability |
| --- | --- | --- | --- | --- |
| target-nf-type | NFType | 1 | This IE shall contain the NF type of the NF Service Producer being discovered. | |
| requester-nf-type | NFType | 1 | This IE shall contain the NF type of the NF Service Consumer that is invoking the Nnrf_NFDiscovery service. | |
| service-names | array(ServiceName) | 1..N | If included, this IE shall contain an array of service names for which the NRF is queried to provide the list of NF profiles. The NRF shall return the NF profiles that have at least one NF service matching the NF service names in this list. The NF service names returned by the NRF shall be an intersection of the NF service names requested and the NF service names registered in the NF profile. If not included, the NRF shall return all the NF service names registered in the NF profile. | |
| requester-nf-instance-fqdn | Fqdn | 0..1 | If included, this IE shall contain the FQDN of the NF Service Consumer that is invoking the Nnrf_NFDiscovery service. The NRF shall use this to return only those NF profiles that include at least one NF service containing an entry in the "allowedNfDomains" list that matches the domain of the requester NF. | |
| target-plmn-list | array(PlmnId) | 1..N | This IE shall be included when NF services in a different PLMN, or NF services of specific PLMN ID(s) in a same PLMN comprising multiple PLMN IDs, need to be discovered. When included, this IE shall contain the PLMN ID of the target NF. If more than one PLMN ID is included, NFs from any PLMN ID present in the list matches the query parameter. | |
| requester-plmn-list | array(PlmnId) | 1..N | This IE shall be included when NF services in a different PLMN need to be discovered. When included, this IE shall contain the PLMN ID(s) of the requester NF. | |
| target-nf-instance-id | NfInstanceId | 0..1 | Identity of the NF instance being discovered. | |
| target-nf-fqdn | Fqdn | 0..1 | FQDN of the target NF instance being discovered. | |
| hnrf-uri | Uri | 0..1 | If included, this IE shall contain the API URI of the NFDiscovery Service of the home NRF. It shall be included if the NF Service Consumer has previously received such API URI to be used for service discovery. | |
| snssais | array(Snssai) | 1..N | If included, this IE shall contain the list of S-NSSAI that are served by the services being discovered. The NRF shall use this to identify the NF services that have registered their support for these S-NSSAIs. The NRF shall return the NF profiles that have at least one S-NSSAI matching the S-NSSAIs in this list. The S-NSSAIs included in the NF profile returned by the NRF shall be an intersection of the S-NSSAIs requested and the S-NSSAIs registered in the NF profile. | |
| plmn-specific-snssai-list | array(PlmnSnssai) | 1..N | If included, this IE shall contain the list of S-NSSAI that are served by the NF service being discovered for the corresponding PLMN provided. The NRF shall use this to identify the NF services that have registered their support for the S-NSSAIs for the corresponding PLMN given. The NRF shall return the NF profiles that have at least one per PLMN S-NSSAI entry matching the PLMN specific S-NSSAIs provided in this list. The per PLMN list of S-NSSAIs included in the NF profile returned by the NRF shall be an intersection of the list requested and the list registered in the NF profile. | |
| nsi-list | array(string) | 1..N | If included, this IE shall contain the list of NSI IDs that are served by the services being discovered. | |
| dnn | Dnn | 0..1 | If included, this IE shall contain the DNN for which NF services serving that DNN is discovered. DNN may be included if the target NF type is "BSF", "SMF" or "UPF". If the Snssai(s) are also included, the NF services serving the DNN shall be available in the network slice(s) identified by the Snssai(s). | |
| smf-serving-area | string | 0..1 | If included, this IE shall contain the serving area of the SMF. It may be included if the target NF type is "UPF". | |
| tai | Tai | 0..1 | Tracking Area Identity. | |
| amf-region-id | AmfRegionId | 0..1 | AMF Region Identity. | |
| amf-set-id | AmfSetId | 0..1 | AMF Set Identity. | |
| guami | Guami | 0..1 | Guami used to search for an appropriate AMF. | |
| supi | Supi | 0..1 | If included, this IE shall contain the SUPI of the requester UE to search for an appropriate NF. SUPI may be included if the target NF type is e.g. "PCF", "CHF", "AUSF", "UDM" or "UDR". | |
| ue-ipv4-address | Ipv4Addr | 0..1 | The IPv4 address of the UE for which a BSF needs to be discovered. | |
| ip-domain | string | 0..1 | The IPv4 address domain of the UE for which a BSF needs to be discovered. | |
| ue-ipv6-prefix | Ipv6Prefix | 0..1 | The IPv6 prefix of the UE for which a BSF needs to be discovered. | |
| pgw-ind | boolean | 0..1 | When present, this IE indicates whether a combined SMF/PGW-C or a standalone SMF needs to be discovered. | |
| pgw | Fqdn | 0..1 | If included, this IE shall contain the PGW FQDN which is received by the AMF from the MME to find the combined SMF/PGW. | |
| gpsi | Gpsi | 0..1 | If included, this IE shall contain the GPSI of the requester UE to search for an appropriate NF. GPSI may be included if the target NF type is "CHF", "UDM" or "UDR". | |
| external-group-identity | GroupId | 0..1 | If included, this IE shall contain the external group identifier of the requester UE to search for an appropriate NF. This may be included if the target NF type is "UDM" or "UDR". | |
| data-set | DataSetId | 0..1 | Indicates the data set to be supported by the NF to be discovered. May be included if the target NF type is "UDR". | |
| routing-indicator | string | 0..1 | Routing Indicator information that allows to route network signalling with SUCI to an AUSF and UDM instance capable to serve the subscriber. May be included if the target NF type is "AUSF" or "UDM". | |
| group-id-list | array(NfGroupId) | 1..N | Identity of the group(s) of the NFs of the target NF type to be discovered. May be included if the target NF type is "UDR", "UDM" or "AUSF". | |
| dnai-list | array(Dnai) | 1..N | If included, this IE shall contain the Data network access identifiers. It may be included if the target NF type is "UPF". | |
| upf-iwk-eps-ind | boolean | 0..1 | When present, this IE indicates whether a UPF supporting interworking with EPS needs to be discovered. | |
| chf-supported-plmn | PlmnId | 0..1 | If included, this IE shall contain the PLMN ID that a CHF supports. This IE may be included when the target NF type is "CHF". | |
| preferred-locality | string | 0..1 | Preferred target NF location (e.g. geographic location, data center). When present, the NRF shall prefer NF profiles with a locality attribute that matches the preferred-locality. | |
| access-type | AccessType | 0..1 | If included, this IE shall contain the Access type which is required to be supported by the target Network Function (i.e. SMF). | |
| supported-features | SupportedFeatures | 0..1 | List of features required to be supported by the target Network Function. This IE may be present only if the service-names attribute is present and if it contains a single service-name, or if the target Network Function does not support any service. It shall be ignored by the NRF otherwise. | Query-Params-Ext1 |
| required-features | array(SupportedFeatures) | 1..N | List of features required to be supported by the target Network Function, as defined by the supportedFeatures attribute in NFService. When present, the required-features attribute shall contain as many entries as the number of entries in the service-names attribute. An entry corresponding to a service for which no specific feature is required shall be encoded as "0". | Query-Params-Ext1 |
| complex-query | ComplexQuery | 0..1 | This query parameter is used to override the default logical relationship of query parameters. | Complex-Query |
| limit | integer | 0..1 | Maximum number of NFProfiles to be returned in the response. | Query-Params-Ext1 |
| max-payload-size | integer | 0..1 | Maximum payload size (before compression, if any) of the response, expressed in kilo octets. When present, the NRF shall limit the number of NF profiles returned in the response such as to not exceed the maximum payload size indicated in the request. Default = 124. Maximum = 2000 (i.e. 2 Mo). | Query-Params-Ext1 |
| pdu-session-types | array(PduSessionType) | 1..N | List of the PDU session type(s) requested to be supported by the target Network Function (i.e. UPF). | Query-Params-Ext1 |

NOTE 1: If this parameter is present and no AMF supporting the requested GUAMI is available due to AMF Failure or planned AMF removal, the NRF shall return in the response AMF instances acting as a backup for AMF failure or planned AMF removal respectively for this GUAMI.
NOTE 2: If the combined SMF/PGW-C is requested to be discovered, the NRF shall return in the response the SMF instances registered with the SmfInfo containing pgwFqdn.
NOTE 3: If a UPF supporting interworking with EPS is requested to be discovered, the NRF shall return in the response the UPF instances registered with the upfInfo containing iwkEpsInd set to true.
NOTE 4: This attribute has a different semantic than what is defined in subclause 6.6.2 of 3GPP TS 29.500 [4], i.e. it is not used to signal optional features of the Nnrf_NFDiscovery Service API supported by the requester NF.

The default logical relationship among the query parameters is logical "AND", i.e. all the provided query parameters shall be matched, with the exception of the "preferred-locality" query (see Table 6.2.3.2.3.1-1).

The NRF may support the Complex query expression as defined in 3GPP TS 29.501 [2] for the NF Discovery service. If the "complexQuery" query parameter is included, then the logical relationship among the query parameters contained in "complexQuery" query parameter is as defined in 3GPP TS 29.571 [7].

A NRF not supporting Complex query expression shall reject a NF service discovery request including a complexQuery parameter, with a ProblemDetails IE including the cause attribute set to INVALID_QUERY_PARAM and the invalidParams attribute indicating the complexQuery parameter.

This method shall support the request data structures specified in table 6.1.3.2.3.1-2 and the response data structures and response codes specified in table 6.1.3.2.3.1-3.

### Table 6.2.3.2.3.1-2: Data structures supported by the GET Request Body on this resource
No request body data structures are defined for this method.

### Table 6.2.3.2.3.1-3: Data structures supported by the GET Response Body on this resource
| Data type | Cardinality | Response code | Description |
| --- | --- | --- | --- |
| SearchResult | 1 | 200 OK | The response body contains the result of the search over the list of registered NF Instances. |
| n/a |  | 307 Temporary Redirect | The response shall be used when the intermediate NRF redirects the service discovery request. |
| ProblemDetails | 1 | 400 Bad Request | The response body contains the error reason of the request message. |
| ProblemDetails | 1 | 403 Forbidden | This response shall be returned if the NF Service Consumer is not allowed to discover the NF Service(s) being queried. |
| ProblemDetails | 1 | 500 Internal Server Error | The response body contains the error reason of the request message. |

##### 6.2.3.2.4 Resource Custom Operations

There are no resource custom operations for the Nnrf_NFDiscovery service in this release of the specification.

### 6.2.4 Custom Operations without associated resources

There are no custom operations defined without any associated resources for the Nnrf_NFDiscovery service in this release of this specification.

### 6.2.5 Notifications

There are no notifications defined for the Nnrf_NFDiscovery service in this release of the specification.

### 6.2.6 Data Model

#### 6.2.6.1 General

This subclause specifies the application data model supported by the API.

### Table 6.2.6.1-1 specifies the data types defined for the Nnrf service based interface protocol.

### Table 6.2.6.1-1: Nnrf_NFDiscovery specific Data Types
| Data type | Section defined | Description |
| --- | --- | --- |
| SearchResult | 6.2.6.2.2 |  |
| NFProfile | 6.2.6.2.3 |  |
| NFService | 6.2.6.2.4 |  |

### Table 6.2.6.1-2 specifies data types re-used by the Nnrf service based interface protocol from other specifications,
including a reference to their respective specifications and when needed, a short description of their use within the Nnrf service based interface.

### Table 6.2.6.1-2: Nnrf_NFDiscovery re-used Data Types
| Data type | Reference | Comments |
| --- | --- | --- |
| Snssai | 3GPP TS 29.571 [7] |  |
| PlmnId | 3GPP TS 29.571 [7] |  |
| Dnn | 3GPP TS 29.571 [7] |  |
| Tai | 3GPP TS 29.571 [7] |  |
| SupportedFeatures | 3GPP TS 29.571 [7] |  |
| NfInstanceId | 3GPP TS 29.571 [7] |  |
| Uri | 3GPP TS 29.571 [7] |  |
| Gpsi | 3GPP TS 29.571 [7] |  |
| GroupId | 3GPP TS 29.571 [7] |  |
| Guami | 3GPP TS 29.571 [7] |  |
| IPv4Addr | 3GPP TS 29.571 [7] |  |
| IPv6Addr | 3GPP TS 29.571 [7] |  |
| UriScheme | 3GPP TS 29.571 [7] |  |
| Dnai | 3GPP TS 29.571 [7] |  |
| NfGroupId | 3GPP TS 29.571 [7] | Identifier of a NF Group |
| PduSessionType | 3GPP TS 29.571 [7] |  |
| DefaultNotificationSubscription | 3GPP TS 29.510 | See clause 6.1.6.2.4 |
| IPEndPoint | 3GPP TS 29.510 | See clause 6.1.6.2.5 |
| NFType | 3GPP TS 29.510 | See clause 6.1.6.3.3 |
| UdrInfo | 3GPP TS 29.510 | See clause 6.1.6.2.6 |
| UdmInfo | 3GPP TS 29.510 | See clause 6.1.6.2.7 |
| AusfInfo | 3GPP TS 29.510 | See clause 6.1.6.2.8 |
| SupiRange | 3GPP TS 29.510 | See clause 6.1.6.2.9 |
| AmfInfo | 3GPP TS 29.510 | See clause 6.1.6.2.11 |
| SmfInfo | 3GPP TS 29.510 | See clause 6.1.6.2.12 |
| UpfInfo | 3GPP TS 29.510 | See clause 6.1.6.2.13 |
| PcfInfo | 3GPP TS 29.510 | See clause 6.1.6.2.20 |
| BsfInfo | 3GPP TS 29.510 | See clause 6.1.6.2.21 |
| ChfInfo | 3GPP TS 29.510 | See clause 6.1.6.2.32 |
| ChfServiceInfo | 3GPP TS 29.510 | See clause 6.1.6.2.33 |
| NFServiceVersion | 3GPP TS 29.510 | See clause 6.1.6.2.19 |
| PlmnSnssai | 3GPP TS 29.510 | See clause 6.1.6.2.44 |
| NFStatus | 3GPP TS 29.510 | See clause 6.1.6.3.7 |
| DataSetId | 3GPP TS 29.510 | See clause 6.1.6.3.8 |
| ServiceName | 3GPP TS 29.510 | See clause 6.1.6.3.11 |
| NFServiceStatus | 3GPP TS 29.510 | See clause 6.1.6.3.12 |

#### 6.2.6.2 Structured data types

##### 6.2.6.2.1 Introduction

This subclause defines the structures to be used in resource representations.

##### 6.2.6.2.2 Type: SearchResult

### Table 6.2.6.2.2-1: Definition of type SearchResult
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| validityPeriod | integer | 1 | It shall contain the time in seconds during which the discovery result is considered valid and can be cached by the NF Service Consumer. This value shall be the same as the value contained in the "max-age" parameter of the "Cache-Control" header field sent in the HTTP response. |
| nfInstances | array(NFProfile) | 0..N | It shall contain an array of NF Instance profiles, matching the search criteria indicated by the query parameters of the discovery request. An empty array means there is no NF instance that can match the search criteria. |
| nrfSupportedFeatures | SupportedFeatures | 0..1 | Features supported by the NRF for the NFDiscovery service. This IE should be present if the NRF supports at least one feature. |

##### 6.2.6.2.3 Type: NFProfile

### Table 6.2.6.2.3-1: Definition of type NFProfile
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| nfInstanceID | NfInstanceId | 1 | Unique identity of the NF Instance. |
| nfType | NFType | 1 | Type of Network Function |
| nfStatus | NFStatus | 1 | Status of the NF Instance |
| plmnList | array(PlmnId) | 1..N | PLMN(s) of the Network Function. This IE shall be present if this information is available for the NF. If not provided, PLMN ID(s) of the PLMN of the NRF are assumed for the NF. |
| sNssais | array(Snssai) | 1..N | S-NSSAIs of the Network Function. If not provided, the NF can serve any S-NSSAI. |
| perPlmnSnssaiList | array(PlmnSnssai) | 1..N | The per-PLMN list of S-NSSAI(s) supported by the Network Function. |
| nsiList | array(string) | 1..N | List of NSIs of the Network Function. If not provided, the NF can serve any NSI. |
| fqdn | Fqdn | 0..1 | FQDN of the Network Function. |
| ipv4Addresses | array(Ipv4Addr) | 1..N | IPv4 address(es) of the Network Function. |
| ipv6Addresses | array(Ipv6Addr) | 1..N | IPv6 address(es) of the Network Function. |
| capacity | integer | 0..1 | Static capacity information in the range of 0-65535, expressed as a weight relative to other NF instances of the same type; if capacity is also present in the nfServiceList parameters, those will have precedence over this value. |
| load | integer | 0..1 | Latest known load information of the NF ranged from 0 to 100 in percentage. |
| locality | string | 0..1 | Operator defined information about the location of the NF instance (e.g. geographic location, data center). |
| priority | integer | 0..1 | Priority (relative to other NFs of the same type) in the range of 0-65535, to be used for NF selection; lower values indicate a higher priority. If priority is also present in the nfServiceList parameters, those will have precedence over this value. |
| udrInfo | UdrInfo | 0..1 | Specific data for the UDR (ranges of SUPI, …) |
| udmInfo | UdmInfo | 0..1 | Specific data for the UDM |
| ausfInfo | AusfInfo | 0..1 | Specific data for the AUSF |
| amfInfo | AmfInfo | 0..1 | Specific data for the AMF (AMF Set ID, …) |
| smfInfo | SmfInfo | 0..1 | Specific data for the SMF (DNN's, …) |
| upfInfo | UpfInfo | 0..1 | Specific data for the UPF (S-NSSAI, DNN, SMF serving area, …) |
| pcfInfo | PcfInfo | 0..1 | Specific data for the PCF |
| bsfInfo | BsfInfo | 0..1 | Specific data for the BSF |
| chfInfo | ChfInfo | 0..1 | Specific data for the CHF |
| customInfo | object | 0..1 | Specific data for custom Network Functions |
| recoveryTime | DateTime | 0..1 | Timestamp when the NF was (re)started |
| nfServicePersistence | boolean | 0..1 | If present, and set to true, it indicates that the different service instances of a same NF Service in the NF instance, supporting a same API version, are capable to persist their resource state in shared storage and therefore these resources are available after a new NF service instance supporting the same API version is selected by a NF Service Consumer. Otherwise, it indicates that the NF Service Instances of a same NF Service are not capable to share resource state inside the NF Instance. |
| nfServices | array(NFService) | 1..N | List of NF Service Instances |
| defaultNotificationSubscriptions | array(DefaultNotificationSubscription) | 1..N | Notification endpoints for different notification types. |

NOTE 1: At least one of the addressing parameters (fqdn, ipv4address or ipv6adress) shall be included in the NF Profile. See NOTE 1 of Table 6.2.6.2.4-1 for the use of these parameters. NOTE 2: The capacity and priority parameters, if present, are used for NF selection and load balancing. The priority and capacity attributes shall be used for NF selection in the same way that priority and weight are used for server selection as defined in IETF RFC 2782 [23]. NOTE 3: If the requester-plmn in the query parameter is different from the PLMN of the discovered NF, then the fqdn attribute value shall contain the interPlmnFqdn value registered by the NF during NF registration (see subclause 6.1.6.2.2). The requester-plmn is different from the PLMN of the discovered NF if it belongs to none of the PLMN ID(s) configured for the PLMN of the NRF. NOTE 4: The usage of the load parameter by the NF service consumer is implementation specific, e.g. be used for NF selection and load balancing, together with other parameters. NOTE 5: An NF may register multiple PLMN IDs in its profile within a PLMN comprising multiple PLMN IDs. If so, all the attributes of the NF Profile shall apply to each PLMN ID registered in the plmnList. As an exception, attributes including a PLMN ID, e.g. IMSI-based SUPI ranges, TAIs and GUAMIs, are specific to one PLMN ID and the NF may register in its profile multiple occurrences of such attributes for different PLMN IDs (e.g. the UDM may register in its profile SUPI ranges for different PLMN IDs). NOTE 6: If notification endpoints are present both in the profile of the NF instance (NFProfile) and in some of its NF Services (NFService) for a same notification type, the notification endpoint(s) of the NF Services shall be used for this notification type.

##### 6.2.6.2.4 Type: NFService

### Table 6.2.6.2.4-1: Definition of type NFService
| Attribute name | Data type | Cardinality | Description |
| --- | --- | --- | --- |
| serviceInstanceID | string | 1 | Unique ID of the service instance within a given NF Instance |
| serviceName | ServiceName | 1 | Name of the service instance (e.g. "udm-sdm") |
| versions | array(NFServiceVersion) | 1..N | The API versions supported by the NF Service and, if available, the corresponding retirement date of the NF Service. The different array elements shall have distinct unique values for `apiVersionInUri`, and consequently, the values of `apiFullVersion` shall have a unique first digit version number. |
| scheme | UriScheme | 1 | URI scheme (e.g. "http", "https") |
| nfServiceStatus | NFServiceStatus | 1 | Status of the NF Service Instance |
| fqdn | string | 0..1 | FQDN of the NF Service Instance. |
| ipEndPoints | array(IpEndPoint) | 1..N | IP address(es) and port information of the Network Function where the service is listening for incoming service requests. |
| apiPrefix | string | 0..1 | Optional path segment(s) used to construct the `apiRoot` variable of the different API URIs. |
| defaultNotificationSubscriptions | array(DefaultNotificationSubscription) | 1..N | Notification endpoints for different notification types. |
| capacity | integer | 0..1 | Static capacity information in the range of 0-65535, expressed as a weight relative to other services of the same type. |
| load | integer | 0..1 | Latest known load information of the NF Service, ranged from 0 to 100 in percentage. |
| priority | integer | 0..1 | Priority (relative to other services of the same type) in the range of 0-65535, to be used for NF Service selection; lower values indicate a higher priority. |
| recoveryTime | DateTime | 0..1 | Timestamp when the NF service was (re)started |
| chfServiceInfo | ChfServiceInfo | 0..1 | Specific data for the CHF service instance |
| supportedFeatures | SupportedFeatures | 0..1 | Supported Features of the NF Service instance |

NOTE 1: The NF Service Consumer shall construct the API URIs of the service using the FQDN and IP address related attributes as described in the note.
NOTE 2: The capacity and priority parameters, if present, are used for service selection and load balancing.
NOTE 3: If the requester-plmn in the query parameter is different from the PLMN of the discovered NF Service, then the fqdn attribute value, if included, shall contain the interPlmnFqdn value registered by the NF Service during NF registration.
NOTE 4: The usage of the load parameter by the NF service consumer is implementation specific.
NOTE 5: If the ipEndPoints attribute is absent in the NF Service and NF Profile, the NF service consumer shall use the fqdn attribute value for DNS query and the default HTTP port if no port number is returned.

#### 6.2.6.3 Simple data types and enumerations

##### 6.2.6.3.1 Introduction

This subclause defines simple data types and enumerations that can be referenced from data structures defined in the previous subclauses.

##### 6.2.6.3.2 Simple data types

The simple data types defined in table 6.2.6.3.2-1 shall be supported.

### Table 6.2.6.3.2-1: Simple data types
| Type Name | Type Definition | Description |
| --- | --- | --- |


### 6.2.7 Error Handling

#### 6.2.7.1 General

HTTP error handling shall be supported as specified in subclause 5.2.4 of 3GPP TS 29.500 [4].

#### 6.2.7.2 Protocol Errors

Protocol errors handling shall be supported as specified in subclause 5.2.7 of 3GPP TS 29.500 [4].

#### 6.2.7.3 Application Errors

The application errors defined for the Nnrf_NFDiscovery service are listed in Table 6.2.7.3-1.

### Table 6.2.7.3-1: Application errors
| Application Error | HTTP status code | Description |
| --- | --- | --- |

### 6.2.8 Security

As indicated in 3GPP TS 33.501 [15], the access to the Nnrf_NFDiscovery API may be authorized by means of the OAuth2 protocol (see IETF RFC 6749 [16]), using the "Client Credentials" authorization grant, where the NRF plays the role of the authorization server.

If Oauth2 authorization is used, an NF Service Consumer, prior to consuming services offered by the Nnrf_NFDiscovery API, shall obtain a "token" from the authorization server, by invoking the Access Token Request service, as described in subclause 5.4.2.2.

NOTE: When multiple NRFs are deployed in a network, the NRF used as authorization server is the same NRF where the Nnrf_NFDiscovery service is invoked by the NF Service Consumer.

The Nnrf_NFDiscovery API defines scopes for OAuth2 authorization as specified in 3GPP TS 33.501 [15]; it defines a single scope consisting on the name of the service (i.e., "nnrf-disc"), and it does not define any additional scopes at resource or operation level.

### 6.2.9 Features supported by the NFDiscovery service

The syntax of the supportedFeatures attribute is defined in subclause 5.2.2 of 3GPP TS 29.571 [7].

The following features are defined for the Nnrf_NFDiscovery service.

### Table 6.2.9-1: Features of supportedFeatures attribute used by Nnrf_NFDiscovery service
| Feature Number | Feature | Description |
| --- | --- | --- |
| 1 | Complex-Query | Support of Complex Query expression (see subclause 6.2.3.2.3.1) |
| 2 | Query-Params-Ext1 | Support of the following query parameters: limit, max-payload-size, required-features, pdu-session-types. |

Feature number: The order number of the feature within the supportedFeatures attribute (starting with 1).
Feature: A short name that can be used to refer to the bit and to the feature.
Description: A clear textual description of the feature.