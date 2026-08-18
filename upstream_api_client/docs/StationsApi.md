# upstream_api_client.StationsApi

All URIs are relative to *http://localhost*

Method | HTTP request | Description
------------- | ------------- | -------------
[**create_station_api_v1_campaigns_campaign_id_stations_post**](StationsApi.md#create_station_api_v1_campaigns_campaign_id_stations_post) | **POST** /api/v1/campaigns/{campaign_id}/stations | Create Station
[**delete_sensor_api_v1_campaigns_campaign_id_stations_delete**](StationsApi.md#delete_sensor_api_v1_campaigns_campaign_id_stations_delete) | **DELETE** /api/v1/campaigns/{campaign_id}/stations | Delete Sensor
[**export_measurements_csv_api_v1_campaigns_campaign_id_stations_station_id_measurements_export_get**](StationsApi.md#export_measurements_csv_api_v1_campaigns_campaign_id_stations_station_id_measurements_export_get) | **GET** /api/v1/campaigns/{campaign_id}/stations/{station_id}/measurements/export | Export Measurements Csv
[**export_sensors_csv_api_v1_campaigns_campaign_id_stations_station_id_sensors_export_get**](StationsApi.md#export_sensors_csv_api_v1_campaigns_campaign_id_stations_station_id_sensors_export_get) | **GET** /api/v1/campaigns/{campaign_id}/stations/{station_id}/sensors/export | Export Sensors Csv
[**get_station_api_v1_campaigns_campaign_id_stations_station_id_get**](StationsApi.md#get_station_api_v1_campaigns_campaign_id_stations_station_id_get) | **GET** /api/v1/campaigns/{campaign_id}/stations/{station_id} | Get Station
[**list_stations_api_v1_campaigns_campaign_id_stations_get**](StationsApi.md#list_stations_api_v1_campaigns_campaign_id_stations_get) | **GET** /api/v1/campaigns/{campaign_id}/stations | List Stations
[**partial_update_station_api_v1_campaigns_campaign_id_stations_station_id_patch**](StationsApi.md#partial_update_station_api_v1_campaigns_campaign_id_stations_station_id_patch) | **PATCH** /api/v1/campaigns/{campaign_id}/stations/{station_id} | Partial Update Station
[**update_station_api_v1_campaigns_campaign_id_stations_station_id_put**](StationsApi.md#update_station_api_v1_campaigns_campaign_id_stations_station_id_put) | **PUT** /api/v1/campaigns/{campaign_id}/stations/{station_id} | Update Station


# **create_station_api_v1_campaigns_campaign_id_stations_post**
> StationCreateResponse create_station_api_v1_campaigns_campaign_id_stations_post(campaign_id, station_create)

Create Station

### Example

* OAuth Authentication (OAuth2PasswordBearer):

```python
import upstream_api_client
from upstream_api_client.models.station_create import StationCreate
from upstream_api_client.models.station_create_response import StationCreateResponse
from upstream_api_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = upstream_api_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

configuration.access_token = os.environ["ACCESS_TOKEN"]

# Enter a context with an instance of the API client
with upstream_api_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = upstream_api_client.StationsApi(api_client)
    campaign_id = 56 # int | 
    station_create = upstream_api_client.StationCreate() # StationCreate | 

    try:
        # Create Station
        api_response = api_instance.create_station_api_v1_campaigns_campaign_id_stations_post(campaign_id, station_create)
        print("The response of StationsApi->create_station_api_v1_campaigns_campaign_id_stations_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling StationsApi->create_station_api_v1_campaigns_campaign_id_stations_post: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **campaign_id** | **int**|  | 
 **station_create** | [**StationCreate**](StationCreate.md)|  | 

### Return type

[**StationCreateResponse**](StationCreateResponse.md)

### Authorization

[OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_sensor_api_v1_campaigns_campaign_id_stations_delete**
> delete_sensor_api_v1_campaigns_campaign_id_stations_delete(campaign_id)

Delete Sensor

### Example

* OAuth Authentication (OAuth2PasswordBearer):

```python
import upstream_api_client
from upstream_api_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = upstream_api_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

configuration.access_token = os.environ["ACCESS_TOKEN"]

# Enter a context with an instance of the API client
with upstream_api_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = upstream_api_client.StationsApi(api_client)
    campaign_id = 56 # int | 

    try:
        # Delete Sensor
        api_instance.delete_sensor_api_v1_campaigns_campaign_id_stations_delete(campaign_id)
    except Exception as e:
        print("Exception when calling StationsApi->delete_sensor_api_v1_campaigns_campaign_id_stations_delete: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **campaign_id** | **int**|  | 

### Return type

void (empty response body)

### Authorization

[OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**204** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **export_measurements_csv_api_v1_campaigns_campaign_id_stations_station_id_measurements_export_get**
> object export_measurements_csv_api_v1_campaigns_campaign_id_stations_station_id_measurements_export_get(campaign_id, station_id, start_date=start_date, end_date=end_date)

Export Measurements Csv

Export measurements for a station as CSV with streaming support.

### Example

* OAuth Authentication (OAuth2PasswordBearer):

```python
import upstream_api_client
from upstream_api_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = upstream_api_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

configuration.access_token = os.environ["ACCESS_TOKEN"]

# Enter a context with an instance of the API client
with upstream_api_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = upstream_api_client.StationsApi(api_client)
    campaign_id = 56 # int | 
    station_id = 56 # int | 
    start_date = '2013-10-20T19:20:30+01:00' # datetime | Start date filter (optional)
    end_date = '2013-10-20T19:20:30+01:00' # datetime | End date filter (optional)

    try:
        # Export Measurements Csv
        api_response = api_instance.export_measurements_csv_api_v1_campaigns_campaign_id_stations_station_id_measurements_export_get(campaign_id, station_id, start_date=start_date, end_date=end_date)
        print("The response of StationsApi->export_measurements_csv_api_v1_campaigns_campaign_id_stations_station_id_measurements_export_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling StationsApi->export_measurements_csv_api_v1_campaigns_campaign_id_stations_station_id_measurements_export_get: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **campaign_id** | **int**|  | 
 **station_id** | **int**|  | 
 **start_date** | **datetime**| Start date filter | [optional] 
 **end_date** | **datetime**| End date filter | [optional] 

### Return type

**object**

### Authorization

[OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **export_sensors_csv_api_v1_campaigns_campaign_id_stations_station_id_sensors_export_get**
> object export_sensors_csv_api_v1_campaigns_campaign_id_stations_station_id_sensors_export_get(campaign_id, station_id)

Export Sensors Csv

Export sensors for a station as CSV with streaming support.

### Example

* OAuth Authentication (OAuth2PasswordBearer):

```python
import upstream_api_client
from upstream_api_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = upstream_api_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

configuration.access_token = os.environ["ACCESS_TOKEN"]

# Enter a context with an instance of the API client
with upstream_api_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = upstream_api_client.StationsApi(api_client)
    campaign_id = 56 # int | 
    station_id = 56 # int | 

    try:
        # Export Sensors Csv
        api_response = api_instance.export_sensors_csv_api_v1_campaigns_campaign_id_stations_station_id_sensors_export_get(campaign_id, station_id)
        print("The response of StationsApi->export_sensors_csv_api_v1_campaigns_campaign_id_stations_station_id_sensors_export_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling StationsApi->export_sensors_csv_api_v1_campaigns_campaign_id_stations_station_id_sensors_export_get: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **campaign_id** | **int**|  | 
 **station_id** | **int**|  | 

### Return type

**object**

### Authorization

[OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_station_api_v1_campaigns_campaign_id_stations_station_id_get**
> GetStationResponse get_station_api_v1_campaigns_campaign_id_stations_station_id_get(station_id, campaign_id)

Get Station

### Example

* OAuth Authentication (OAuth2PasswordBearer):

```python
import upstream_api_client
from upstream_api_client.models.get_station_response import GetStationResponse
from upstream_api_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = upstream_api_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

configuration.access_token = os.environ["ACCESS_TOKEN"]

# Enter a context with an instance of the API client
with upstream_api_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = upstream_api_client.StationsApi(api_client)
    station_id = 56 # int | 
    campaign_id = 56 # int | 

    try:
        # Get Station
        api_response = api_instance.get_station_api_v1_campaigns_campaign_id_stations_station_id_get(station_id, campaign_id)
        print("The response of StationsApi->get_station_api_v1_campaigns_campaign_id_stations_station_id_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling StationsApi->get_station_api_v1_campaigns_campaign_id_stations_station_id_get: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **station_id** | **int**|  | 
 **campaign_id** | **int**|  | 

### Return type

[**GetStationResponse**](GetStationResponse.md)

### Authorization

[OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **list_stations_api_v1_campaigns_campaign_id_stations_get**
> ListStationsResponsePagination list_stations_api_v1_campaigns_campaign_id_stations_get(campaign_id, page=page, limit=limit)

List Stations

### Example

* OAuth Authentication (OAuth2PasswordBearer):

```python
import upstream_api_client
from upstream_api_client.models.list_stations_response_pagination import ListStationsResponsePagination
from upstream_api_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = upstream_api_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

configuration.access_token = os.environ["ACCESS_TOKEN"]

# Enter a context with an instance of the API client
with upstream_api_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = upstream_api_client.StationsApi(api_client)
    campaign_id = 56 # int | 
    page = 1 # int |  (optional) (default to 1)
    limit = 20 # int |  (optional) (default to 20)

    try:
        # List Stations
        api_response = api_instance.list_stations_api_v1_campaigns_campaign_id_stations_get(campaign_id, page=page, limit=limit)
        print("The response of StationsApi->list_stations_api_v1_campaigns_campaign_id_stations_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling StationsApi->list_stations_api_v1_campaigns_campaign_id_stations_get: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **campaign_id** | **int**|  | 
 **page** | **int**|  | [optional] [default to 1]
 **limit** | **int**|  | [optional] [default to 20]

### Return type

[**ListStationsResponsePagination**](ListStationsResponsePagination.md)

### Authorization

[OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **partial_update_station_api_v1_campaigns_campaign_id_stations_station_id_patch**
> StationCreateResponse partial_update_station_api_v1_campaigns_campaign_id_stations_station_id_patch(campaign_id, station_id, station_update)

Partial Update Station

### Example

* OAuth Authentication (OAuth2PasswordBearer):

```python
import upstream_api_client
from upstream_api_client.models.station_create_response import StationCreateResponse
from upstream_api_client.models.station_update import StationUpdate
from upstream_api_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = upstream_api_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

configuration.access_token = os.environ["ACCESS_TOKEN"]

# Enter a context with an instance of the API client
with upstream_api_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = upstream_api_client.StationsApi(api_client)
    campaign_id = 56 # int | 
    station_id = 56 # int | 
    station_update = upstream_api_client.StationUpdate() # StationUpdate | 

    try:
        # Partial Update Station
        api_response = api_instance.partial_update_station_api_v1_campaigns_campaign_id_stations_station_id_patch(campaign_id, station_id, station_update)
        print("The response of StationsApi->partial_update_station_api_v1_campaigns_campaign_id_stations_station_id_patch:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling StationsApi->partial_update_station_api_v1_campaigns_campaign_id_stations_station_id_patch: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **campaign_id** | **int**|  | 
 **station_id** | **int**|  | 
 **station_update** | [**StationUpdate**](StationUpdate.md)|  | 

### Return type

[**StationCreateResponse**](StationCreateResponse.md)

### Authorization

[OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **update_station_api_v1_campaigns_campaign_id_stations_station_id_put**
> StationCreateResponse update_station_api_v1_campaigns_campaign_id_stations_station_id_put(station_id, campaign_id, station_update)

Update Station

### Example

* OAuth Authentication (OAuth2PasswordBearer):

```python
import upstream_api_client
from upstream_api_client.models.station_create_response import StationCreateResponse
from upstream_api_client.models.station_update import StationUpdate
from upstream_api_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = upstream_api_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

configuration.access_token = os.environ["ACCESS_TOKEN"]

# Enter a context with an instance of the API client
with upstream_api_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = upstream_api_client.StationsApi(api_client)
    station_id = 56 # int | 
    campaign_id = 56 # int | 
    station_update = upstream_api_client.StationUpdate() # StationUpdate | 

    try:
        # Update Station
        api_response = api_instance.update_station_api_v1_campaigns_campaign_id_stations_station_id_put(station_id, campaign_id, station_update)
        print("The response of StationsApi->update_station_api_v1_campaigns_campaign_id_stations_station_id_put:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling StationsApi->update_station_api_v1_campaigns_campaign_id_stations_station_id_put: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **station_id** | **int**|  | 
 **campaign_id** | **int**|  | 
 **station_update** | [**StationUpdate**](StationUpdate.md)|  | 

### Return type

[**StationCreateResponse**](StationCreateResponse.md)

### Authorization

[OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

