# Freeimage.host API v1 Documentation

## API version 1

Freeimage.host's API v1 allows you to upload pictures.

## API Key

```
6d207e02198a847aa98d0a2a901485a5
```

## API Call

### Request Method

API v1 calls can be performed using the **POST** or **GET** request methods. However, since GET requests are limited by the maximum allowed length of a URL, it is recommended to use the POST request method.

### Request URL

```
https://freeimage.host/api/1/upload
```

### Parameters

| Parameter | Required | Description                                                                                             |
| --------- | -------- | ------------------------------------------------------------------------------------------------------- |
| `key`     | Yes      | The API key.                                                                                            |
| `action`  | No       | Action to perform \[values: upload].                                                                    |
| `source`  | No       | Either an image URL or a base64 encoded image string. FILES\["source"] can also be used in the request. |
| `format`  | No       | Return format \[values: json (default), redirect, txt].                                                 |

### Example Call

```
GET http://freeimage.host/api/1/upload/?key=12345&source=http://somewebsite/someimage.jpg&format=json
```

> **Note:** Always use **POST** when uploading local files. URL encoding may alter the base64 source due to encoded characters or by URL request length limit in a GET request.

## API Response

API v1 responses provide all the uploaded image information in **JSON** format.

### Example Response (JSON)

```json
{
  "status_code": 200,
  "success": {
    "message": "image uploaded",
    "code": 200
  },
  "image": {
    "name": "example",
    "extension": "png",
    "size": 53237,
    "width": 1151,
    "height": 898,
    "date": "2014-06-04 15:32:33",
    "date_gmt": "2014-06-04 19:32:33",
    "storage_id": null,
    "description": null,
    "nsfw": "0",
    "md5": "c684350d722c956c362ab70299735830",
    "storage": "datefolder",
    "original_filename": "example.png",
    "original_exifdata": null,
    "views": "0",
    "id_encoded": "L",
    "filename": "example.png",
    "ratio": 1.2817371937639,
    "size_formatted": "52 KB",
    "mime": "image/png",
    "bits": 8,
    "channels": null,
    "url": "http://freeimage.host/images/2014/06/04/example.png",
    "url_viewer": "http://freeimage.host/image/L",
    "thumb": {
      "filename": "example.th.png",
      "name": "example.th",
      "width": 160,
      "height": 160,
      "ratio": 1,
      "size": 17848,
      "size_formatted": "17.4 KB",
      "mime": "image/png",
      "extension": "png",
      "bits": 8,
      "channels": null,
      "url": "http://freeimage.host/images/2014/06/04/example.th.png"
    },
    "medium": {
      "filename": "example.md.png",
      "name": "example.md",
      "width": 500,
      "height": 390,
      "ratio": 1.2820512820513,
      "size": 104448,
      "size_formatted": "102 KB",
      "mime": "image/png",
      "extension": "png",
      "bits": 8,
      "channels": null,
      "url": "http://freeimage.host/images/2014/06/04/example.md.png"
    },
    "views_label": "views",
    "display_url": "http://freeimage.host/images/2014/06/04/example.md.png",
    "how_long_ago": "moments ago"
  },
  "status_txt": "OK"
}
```

### Response Fields

* `status_code`: HTTP status code of the response.
* `success`: Contains the status message and code.
* `image`: Object containing detailed image data.
* `thumb`: Thumbnail version of the image.
* `medium`: Medium-sized version of the image.
* `views_label`: Label for the views count.
* `display_url`: URL of the displayed image.
* `how_long_ago`: Relative time since the upload.
