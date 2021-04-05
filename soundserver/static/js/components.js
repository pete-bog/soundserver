Vue.component('file-table', {
    data: function () {
        return {
            files: []
        };
    },
    template: `<ul>
            <li v-for="file in files">
                <a v-bind:href="file.url">{{ file.name }}</a>
                <button class="btn btn-primary" v-on:click="preview">
                    <i class="bi bi-play-fill"></i>
                </button>
                <button class="btn btn-primary" v-on:click="edit">
                    <i class="bi bi-pen-fill"></i>
                </button>
            </li>
        </ul>`,
    mounted: function () {
        axios.get("/files")
            .then((response) => {
                this.files = response.data.files
            })
            .catch((error) => {
                console.log(error)
            });
    },
    methods: {
        preview: function (event) {
            let parent = event.target.parentNode;
            while (parent.nodeName != "LI") {
                parent = parent.parentNode;
            }
            let url = parent.querySelector('a').getAttribute('href');
            let audio = new Audio(url);
            audio.addEventListener('loadeddata', () => {
                audio.play();
            });
        },
        edit: function (event) {
            let parent = event.target.parentNode;
            while (parent.nodeName != "LI") {
                parent = parent.parentNode;
            }
            let name = encodeURIComponent(parent.querySelector('a').innerHTML);
            // Simulate a mouse click:
            window.location.href = "/static/edit.html?name=" + name;
        }
    }
});