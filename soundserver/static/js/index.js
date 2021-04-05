function makeTableRow(data) {
    let row = document.createElement("tr");
    let name = document.createElement("td");
    name.innerHTML = `<a href="${data.url}">${data.name}</a>`
    row.appendChild(name);

    let actions = document.createElement("td");
    actions.innerHTML = `<a>Preview</a><a href="/edit?name=${data.name}">Edit</a>`
    row.appendChild(actions)
    return row;
}

function loadLocalFiles() {
    let table = document.getElementById("local-files");
    axios.get("/files")
        .then(function (response) {
            for (entry of response.data.files) {
                let row = makeTableRow(entry);
                table.appendChild(row);
            }
        })
        .catch(function (error) {
            let errorElem = document.createElement("p");
            errorElem.innerHTML = "There was an error retrieving files: " + error
            table.parentNode.appendChild(errorElem)
        });
}

function onLoad() {
    loadLocalFiles();
}

document.addEventListener("DOMContentLoaded", onLoad);