var AJAX_TIMEOUT = 300000;
var MAX_RETRIES = 1;

/**
 * Handle an error from the AJAX request
 * retry the request in case of timeout
 * maximum retries: 10
 * each retry is performed after an exponential delay
 * 
 * @param jqXHR
 * 	the jQuery XMLHttpRequest
 * @param textStatus
 * 	the string describing the type of error
 * @param errorThrown
 * 	the textual portion of the HTTP status
 * @param retryCallback
 * 	the AJAX request to be retried
 * @param url
 * 	the request url
 * @param obj
 * 	the parameters (in a dictionary form) for the POST request
 * @param async
 * 	the operation type (sync or async)
 * @param successCallback
 * 	the success callback function
 * @param param
 * 	the parameters for the success callback function
 * @param errorCallback
 * 	the error callback function
 * @param count
 * 	the number of retries already performed
 */
function handleError(jqXHR, textStatus, errorThrown, retryCallback, url, contentType, processData, obj, async, successCallback, param, errorCallback, count) {
	var retry = false;
	
	switch(jqXHR.status) {
	case 0:		// client timeout
	case 408:	// server timeout
	case 503:	// Service Unavailable
	case 504:	// Gateway Timeout
		retry = (count <= MAX_RETRIES);
		break;
	}
	
	if (!retry) {
		var msg = '';
		var err = jqXHR.status;
		if (err != null) {
			msg += 'Status: ' + err + '\n';
		}
		err = jqXHR.responseText;
		if (err != null) {
			msg += 'ResponseText: ' + err + '\n';
		}
		if (textStatus != null) {
			msg += 'TextStatus: ' + textStatus + '\n';
		}
		if (errorThrown != null) {
			msg += 'ErrorThrown: ' + errorThrown + '\n';
		}
		msg += 'URL: ' + url + '\n';
		document.body.style.cursor = 'default';
		alert(msg);
	} else {
		var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
		setTimeout(function(){retryCallback(url, contentType, processData, obj, async, successCallback, param, errorCallback, count+1);}, delay);
	}
}

var restAJAX = {
		POST: function(url, contentType, processData, obj, async, successCallback, param, errorCallback, count) {
			document.body.style.cursor = 'wait';
			$.ajax({
				url: url,
				contentType: contentType,
				headers: make_headers(),
				type: 'POST',
				data: (processData ? obj : JSON.stringify(obj)),
				dataType: 'text',
				timeout: AJAX_TIMEOUT,
				async: async,
				processData: processData,
				success: function(data, textStatus, jqXHR) {
					document.body.style.cursor = 'default';
					successCallback(data, textStatus, jqXHR, param);
				},
				error: function(jqXHR, textStatus, errorThrown) {
					if (errorCallback == null) {
						handleError(jqXHR, textStatus, errorThrown, restAJAX.POST, url, contentType, processData, obj, async, successCallback, param, errorCallback, count);
					} else {
						errorCallback(jqXHR, textStatus, errorThrown, restAJAX.POST, url, contentType, processData, obj, async, successCallback, param, errorCallback, count);
					}
				}
			});
		},
		GET: function(url, contentType, async, successCallback, param, errorCallback, count) {
			restAJAX.fetch(url, contentType, true, [], async, successCallback, param, errorCallback, count);
		},
		fetch: function(url, contentType, processData, obj, async, successCallback, param, errorCallback, count) {
			document.body.style.cursor = 'wait';
			$.ajax({
				url: url,
				contentType: contentType,
				headers: make_headers(),
				timeout: AJAX_TIMEOUT,
				async: async,
				accepts: {text: 'application/json'},
				processData: processData,
				data: (processData ? obj : JSON.stringify(obj)),
				dataType: 'json',
				success: function(data, textStatus, jqXHR) {
					document.body.style.cursor = 'default';
					successCallback(data, textStatus, jqXHR, param);
				},
				error: function(jqXHR, textStatus, errorThrown) {
					if (errorCallback == null) {
						handleError(jqXHR, textStatus, errorThrown, restAJAX.fetch, url, contentType, processData, obj, async, successCallback, param, errorCallback, count);
					} else {
						errorCallback(jqXHR, textStatus, errorThrown, restAJAX.fetch, url, contentType, processData, obj, async, successCallback, param, errorCallback, count);
					}
				}
			});
		},
		DELETE: function(url, async, successCallback, param, errorCallback, count) {
			restAJAX.remove(url, null, true, null, async, successCallback, param, errorCallback, count);
		},
		remove: function(url, contentType, processData, obj, async, successCallback, param, errorCallback, count) {
			document.body.style.cursor = 'wait';
			$.ajax({
				url: url,
				headers: make_headers(),
				type: 'DELETE',
				timeout: AJAX_TIMEOUT,
				async: async,
				dataType: 'text',
				success: function(data, textStatus, jqXHR) {
					document.body.style.cursor = 'default';
					successCallback(data, textStatus, jqXHR, param);
				},
				error: function(jqXHR, textStatus, errorThrown) {
					if (errorCallback == null) {
						handleError(jqXHR, textStatus, errorThrown, restAJAX.remove, url, contentType, processData, obj, async, successCallback, param, errorCallback, count);
					} else {
						errorCallback(jqXHR, textStatus, errorThrown, restAJAX.remove, url, contentType, processData, obj, async, successCallback, param, errorCallback, count);
					}
				}
			});
		},
		PUT: function(url, contentType, processData, obj, async, successCallback, param, errorCallback, count) {
			document.body.style.cursor = 'wait';
			$.ajax({
				url: url,
				contentType: contentType,
				headers: make_headers(),
				type: 'PUT',
				data: (processData ? obj : JSON.stringify(obj)),
				dataType: 'json',
				timeout: AJAX_TIMEOUT,
				processData: processData,
				async: async,
				success: function(data, textStatus, jqXHR) {
					document.body.style.cursor = 'default';
					successCallback(data, textStatus, jqXHR, param);
				},
				error: function(jqXHR, textStatus, errorThrown) {
					if (errorCallback == null) {
						handleError(jqXHR, textStatus, errorThrown, restAJAX.PUT, url, contentType, processData, obj, async, successCallback, param, errorCallback, count);
					} else {
						errorCallback(jqXHR, textStatus, errorThrown, restAJAX.PUT, url, contentType, processData, obj, async, successCallback, param, errorCallback, count);
					}
				}
			});
		}
};

function initTable() {
	getTableMetadata();
}

function getTableMetadata() {
	var url = '' + window.location;
	restAJAX.GET(url, 'application/x-www-form-urlencoded; charset=UTF-8', true, postGetTableMetadata, null, null, 2);
}

function postGetTableMetadata(data, textStatus, jqXHR, param) {
	var schema = data['schema_name'];
	var table = data['table_name'];
	displaySchema(schema, data);
	//alert(JSON.stringify(data, null, 4));
}

function initSchema() {
	getSchemaMetadata();
}

function getSchemaMetadata() {
	var url = '' + window.location;
	restAJAX.GET(url, 'application/x-www-form-urlencoded; charset=UTF-8', true, postGetSchemaMetadata, null, null, 2);
}

function postGetSchemaMetadata(data, textStatus, jqXHR, param) {
	var schema = data['schema_name'];
	displaySchema(schema, data);
}

function initSchemas() {
	getMetadata();
}

function make_headers() {
	var res = {'User-agent': 'ERMREST/1.0'};
	return res;
}

function getMetadata() {
	var url = '' + window.location;
	restAJAX.GET(url, 'application/x-www-form-urlencoded; charset=UTF-8', true, postGetMetadata, null, null, 2);
}

function postGetMetadata(data, textStatus, jqXHR, param) {
	var schemas = data['schemas'];
	$.each(schemas, function(key, value) {
		displaySchema(key, value);
	});
}

function displaySchema(name, value) {
	var ermrestDiv = $('#ermrest');
	ermrestDiv.append($('<br>'));
	ermrestDiv.append($('<br>'));
	var schemaDiv = $('<div>');
	ermrestDiv.append(schemaDiv);
	schemaDiv.addClass('schema');
	var h1 = $('<h1>');
	schemaDiv.append(h1);
	h1.html('Schema: ' + name);
	if (value['tables'] != null) {
		$.each(value['tables'], function(tableName, table) {
			displayTable(schemaDiv, tableName, table);
		});
	} else {
		displayTable(schemaDiv, value['table_name'], value);
	}
}

function displayTable(schemaDiv, name, value) {
	var tableDiv = $('<div>');
	schemaDiv.append(tableDiv);
	tableDiv.addClass('dbtable');
	var h2 = $('<h2>');
	tableDiv.append(h2);
	h2.html('Table: ' + name);
	
	if (value['comment'] != null) {
		var h3 = $('<h3>');
		tableDiv.append(h3);
		h3.html('Description:'); 
		var ul = $('<ul>');
		tableDiv.append(ul);
		var li = $('<li>');
		ul.append(li);
		li.html(value['comment']);
	}

	var h3 = $('<h3>');
	tableDiv.append(h3);
	var ul = $('<ul>');
	h3.html('Columns:'); 
	tableDiv.append(ul);
	$.each(value['column_definitions'], function(i, key) {
		displayColumn(ul, key);
	});

	if (value['keys'].length > 0) {
		var h3 = $('<h3>');
		tableDiv.append(h3);
		var ul = $('<ul>');
		h3.html('Keys:'); 
		tableDiv.append(ul);
		$.each(value['keys'], function(i, key) {
			displayKey(ul, key);
		});
	}

	if (value['foreign_keys'].length > 0) {
		var h3 = $('<h3>');
		tableDiv.append(h3);
		var ul = $('<ul>');
		h3.html('Foreign Keys:'); 
		tableDiv.append(ul);
		$.each(value['foreign_keys'], function(i, key) {
			displayForeignKey(ul, key);
		});
	}
	schemaDiv.append($('<br>'));
	schemaDiv.append($('<br>'));
}

function displayKey(ul, value) {
	$.each(value, function(name, key) {
		var values = [];
		$.each(key, function(i, keyName) {
			values.push(keyName);
		});
		var li = $('<li>');
		ul.append(li);
		li.html('(' + values.join(', ') + ')');
	});
}

function displayForeignKey(ul, value) {
	var foreign_key_columns = value['foreign_key_columns'];
	var referenced_columns = value['referenced_columns'];
	var foreignValues = [];
	var referencedValues = [];
	var prefix = null;
	$.each(foreign_key_columns, function(i, foreign_key_column) {
		var referenced_column = referenced_columns[i];
		prefix = referenced_column['schema_name'] + '.' + referenced_column['table_name'];
		foreignValues.push(foreign_key_column['column_name']);
		referencedValues.push(referenced_column['column_name']);
	});
	var li = $('<li>');
	ul.append(li);
	li.html('(' + foreignValues.join(', ') + ') references ' + prefix + ' (' +  referencedValues.join(', ') + ')');
}

function displayColumn(ul, value) {
	var li = $('<li>');
	ul.append(li);
	li.html(value['name'] + ': ' +  value['type']);
	if (value['comment'] != null) {
		var comment = $('<ul>');
		li.append(comment);
		var li = $('<li>');
		comment.append(li);
		li.html(value['comment']);
	}
}

