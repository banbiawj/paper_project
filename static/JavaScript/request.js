// const { type } = require("os");

new Vue({
    el: '#app',
    data: {
        API_BASE: "/api/v1", // FastAPI 地址前缀

        TypeName:"idiom",
        PresentPath:"词库",//当前书籍
        FavoriteName:"query.json",//当前收藏夹

        idiom_BookshelfList_list:[],
        words_BookshelfList_list:[],
        BookshelfList_list:[],

        idiom_FavoriteList_list:[],
        words_FavoriteList_list:[],
        FavoriteList_list:[],

        createFavoriteName: "",//用于创建收藏夹
        CreateBookName:"",
        // createType: "idiom",

        // saveFavoriteName: "default.json",
        // saveType: "idiom",
        // saveWord: "",
        // saveExplain: "",

        // alterFavoriteName: "",
        // alterType: "idiom",
        // alterWord: "",
        // alterExplain: "",
        alterMessage:{},

        // readFavoriteName: "default.json",
        // readType: "idiom",

        resultOutput: [],

        // 查看数据
        checkindex:0,

        // 查询数据
        inquireContent: "",
        queryType: "idiom",
        result: [],
        errorMessage: "",
        loading: false,

        // 自导入
        diywords:"",
        diyexplain:"",
        fields: [],

        // model框声明
        queryModal:null,
        amendModal:null,
        dynamicModal:null,
        exampleModal:null,
        CreateBookModal:null,

    },
    created() {
        this.FavoriteList("词库")
        this.BookshelfList()
        this.readData("query.json")
    },
    mounted() {

    },
computed: {
    currentEntryList() {
            if (this.resultOutput && this.resultOutput[this.checkindex]) {
            return Object.entries(this.resultOutput[this.checkindex])
            }
            return []
    },

    },

    methods: {
        // 转换TypeName
        transform_TypeName(){
            this.TypeName = this.TypeName=='idiom' ? 'words':'idiom';

            if(this.TypeName=='words'){
                this.BookshelfList_list = this.words_BookshelfList_list
                this.FavoriteList_list = this.words_FavoriteList_list
            }
            else if(this.TypeName=='idiom'){
                this.BookshelfList_list = this.idiom_BookshelfList_list
                this.FavoriteList_list = this.idiom_FavoriteList_list
            }
            this.PresentPath = "词库"
            this.FavoriteName = "query.json" 
            this.readData("query.json")
        },
        // 初始化书架列表
        async BookshelfList() {
            try {
                const res = await fetch(`${this.API_BASE}/DisplayContent/BookshelfList`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                });
                const json = await res.json();
                console.log(json.data); 
                this.idiom_BookshelfList_list = json.data.idiom_BookshelfList_list;
                this.words_BookshelfList_list = json.data.words_BookshelfList_list;
                console.log(this.idiom_BookshelfList_list);
                // this.FavoriteList_list = this.idiom_FavoriteList_list
                if(this.TypeName=='words'){
                    this.BookshelfList_list = this.words_BookshelfList_list
                }
                else if(this.TypeName=='idiom'){
                    this.BookshelfList_list = this.idiom_BookshelfList_list
                }

            } catch (e) { 
                console.error("请求出错:", e);
                this.resultOutput = `请求出错: ${e}`; 
            }
        },
        // 初始化收藏夹列表
        async FavoriteList(BookName) {
            try {
                this.PresentPath = BookName;//即请求的书下的收藏夹列表
                const res = await fetch(`${this.API_BASE}/DisplayContent/FavoriteList`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ 
                        TypeName: this.TypeName, 
                        BookName: this.PresentPath
                    })
                });
                const json = await res.json();
                console.log(json.data); 
                this.FavoriteList_list = json.data.FavoriteList_list;
                this.FavoriteName = "query.json"
                this.readData("query.json")
                console.log(this.FavoriteList_list);
            } catch (e) { 
                console.error("请求出错:", e);
                this.resultOutput = `请求出错: ${e}`; 
            }
        },
        hideModal(id) {
            const modalEl = document.getElementById(id);
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl); // 如果还没创建就创建
            modal.hide();
        },
        showModal(id) {
            const modalEl = document.getElementById(id);
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl); // 如果还没创建就创建
            modal.show();
        },
        // 创建书籍
        async createBook() {
            try {
                const res = await fetch(`${this.API_BASE}/DisplayContent/CreateBook`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ 
                        TypeName: this.TypeName, 
                        BookName: this.CreateBookName
                    })
                });

                const response = await res.json();
                if (response.code === 200) {
                    // this.FavoriteList()
                    this.hideModal("CreateBookModal")
                    this.BookshelfList_list = response.data
                    this.CreateBookName=null
                } else {
                    console.error('请求失败:', response.message);
                }
                
                console.log('实际数据:', this.resultOutput);
            } catch (e) { 
                console.log( '请求出错:',e)
            }
        },
        // 创建收藏夹
        async createFavorite() {
            try {
                const res = await fetch(`${this.API_BASE}/DataOperate/CreateFavorite`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ 
                        TypeName: this.TypeName, 
                        FavoriteName: this.createFavoriteName,
                        PresentPath:this.PresentPath
                    })
                });

                const response = await res.json();
                if (response.code === 200) {
                    this.FavoriteList(this.PresentPath)
                    this.hideModal("exampleModal")
                    this.createFavoriteName=null
                } else {
                    console.error('请求失败:', response.message);
                }
                
                console.log('实际数据:', this.resultOutput);
            } catch (e) { 
                console.log( '请求出错:',e)
            }
        },
        // 保存数据
        async saveData(messages,ModelId) {
            // if(this.readType)
            // {
            //     this.saveType = this.readType
            //     this.saveFavoriteName = this.readFavoriteName
            // }
            try {
                const res = await fetch(`${this.API_BASE}/DataOperate/SaveData`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        TypeName: this.TypeName,
                        FavoriteName: this.FavoriteName,
                        PresentPath:this.PresentPath,
                        message: messages
                    })
                });
                // this.resultOutput = JSON.stringify(await res.json(), null, 2);
                // readData(this.saveFavoriteName)
                const response = await res.json();
                console.log(messages)
                console.log(typeof messages)
                            // 检查响应状态
                if (response.code === 200) {
                    // this.resultOutput = response.data;  // 只取data部分
                    this.readData(this.FavoriteName)
                    this.hideModal(ModelId)
                    console.log('实际数据:', this.resultOutput);
                } else {
                    console.error('请求失败:', response.message);
                    this.resultOutput = [];
                }
                
                console.log('实际数据:', this.resultOutput);
            } catch (e) { 
                this.resultOutput = `请求出错: ${e}`; 
            }
        },
        // 修改数据
        async alterData(item) {
            const type=item['type']
            const favorite=item['favoritename']


            try {
                const res = await fetch(`${this.API_BASE}/DataOperate/alterData`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        TypeName: type,
                        FavoriteName: favorite,
                        PresentPath:this.PresentPath,
                        message: item 
                    })
                });
                // this.resultOutput = JSON.stringify(await res.json(), null, 2);
                const response = await res.json();
                if (response.code === 200) {
                    // this.resultOutput = response.data;  // 只取data部分
                    this.readData(this.saveFavoriteName)
                    this.hideModal("amendModal")
                    console.log('实际数据:', this.resultOutput);
                } else {
                    console.error('请求失败:', response.message);
                    this.resultOutput = [];
                }
                
                console.log('实际数据:', this.resultOutput);
            } catch (e) { 
                this.resultOutput = `请求出错: ${e}`; 
            }
        },
        // 删除数据
        async deleteData(item) {
            // const type=item['type']
            // const favorite=item['favoritename']
            const word=item['word']

            try {
                const res = await fetch(`${this.API_BASE}/DataOperate/DeleteData`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        TypeName: this.TypeName,
                        FavoriteName:this.FavoriteName,
                        PresentPath:this.PresentPath,
                        message: { word: word }
                    })
                });
                const response = await res.json();
                
                // 检查响应状态
                if (response.code === 200) {
                    this.resultOutput = response.data;  // 只取data部分
                    console.log('实际数据:', this.resultOutput);
                } else {
                    console.error('请求失败:', response.message);
                    this.resultOutput = [];
                }
                
                console.log('实际数据:', this.resultOutput);
            } catch (e) { 
                this.resultOutput = `请求出错: ${e}`; 
            }
        },
        // 获取数据
        async readData(readFavoriteName) {
            this.FavoriteName = readFavoriteName;
            try {
                const res = await fetch(`${this.API_BASE}/DataOperate/ReadData`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        TypeName: this.TypeName,
                        FavoriteName: this.FavoriteName,
                        PresentPath:this.PresentPath
                        
                    })
                });
                const response = await res.json();
                
                // 检查响应状态
                if (response.code === 200) {
                    
                    this.resultOutput = response.data.reverse();  // 只取data部分
                    
                    console.log('实际数据:', this.resultOutput);
                } else {
                    console.error('请求失败:', response.message);
                    this.resultOutput = [];
                }
                
                console.log('实际数据:', this.resultOutput);
            } catch (e) { 
                this.resultOutput = `请求出错: ${e}`; 
            }
        },

        // 查询数据
        async sendQuery() {
          this.result = [];
          this.errorMessage = "";
          this.loading = true;

          try {
            const response = await fetch(`${this.API_BASE}/inquire/query`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json"
              },
              body: JSON.stringify({
                TypeName: this.TypeName,
                InquireContent: this.inquireContent
              })
            });
            

            if (!response.ok) {
              throw new Error("服务器错误: " + response.status);
            }

            const data = await response.json();
            if (data.code === 200) {
              this.result = data.data[0];
              this.hideModal('query-before-Modal')
              this.showModal('queryModal')

              console.log(data.data);
            } else {
              this.errorMessage = data.message || "未知错误";
            }
          } catch (err) {
            this.errorMessage = "请求失败: " + err.message;
          } finally {
            this.loading = false;
          }
        },

        // 自导入
        setfields(){
            this.fields=[
                { key:'word', value:  ''},
                { key:'explain', value: ''},
                { key:'note', value: ''},
            ]
        },
        addField() {
        this.fields.push({ key:' ', value: '' });
        },
        removeField(index) {
            console.log('removeField called with index:', this.fields);
            this.fields.splice(index, 1); 
            console.log('removeField called with index after:', this.fields);
        },
        submitForm() {
            // this.fields[0].value=this.diywords;
            // this.fields[1].value=this.diyexplain;

            console.log("提交的数据：", this.fields);
            // alert(JSON.stringify(this.fields))

            const result = this.fields.reduce((obj, item) => {
            // 去掉多余空格，保证 key 干净
            obj[item.key.trim()] = item.value;
            return obj;
            }, {});

            console.log(result);

            // alert("提交内容: " + JSON.stringify(this.fields.map(f => f.value)));
            this.saveData(result,"dynamicModal")
            },

        alert_submitForm() {
            const result = this.fields.reduce((obj, item) => {
                // 添加空值检查
                if (item.key && item.key.trim()) {
                    obj[item.key.trim()] = item.value;
                }
                return obj;
            }, {});
            
            this.alterMessage = result
            console.log("反转回的数据"+this.alterMessage )
            this.alterData(result)
        },
        
        reverseForm(data) {
            return Object.entries(data).map(([key, value]) => ({
                key: key,
                value: value
            }));
        },


        setAlterMessage(item){
                this.alterMessage = item;
                this.fields= this.reverseForm(item)
                console.log("反转后的数据"+this.fields )
            },
        
        setcheckindex(index){
            this.checkindex =index;
        },
        alertcheckindex(symbol) {
        const length = this.resultOutput.length;
        
        switch(symbol) {
            case "+":
            // 循环前进：到达最后一项时跳转到第一项
            this.checkindex = (this.checkindex + 1) % length;
            break;
            
            case "-":
            // 循环后退：到达第一项时跳转到最后一项
            this.checkindex = (this.checkindex - 1 + length) % length;
            break;
        }
        
        return this.checkindex;
        },
        translate(key){
            switch(key){
                case "word":
                    return"成语";
                case "explain":
                    return"基本释义";
                case "nature":
                    return"词性";
                case "note":
                    return"笔记";
                case "emphasis":
                    return"侧重点";
                case "derivation":
                    return"出处";
                case "collocation":
                    return"搭配";
                case "example":
                    return"例句";
                case "favoritename":
                    return"收藏夹";
                case "default":
                    return"默认";
                case "query":
                    return"全部";
                }
            return key
            },
        removeAfterLastDot(str) {
          return str.includes('.') ? str.substring(0, str.lastIndexOf('.')) : str;
        },
        Selectesd(idiom_FavoriteList){
            if (readFavoriteName==idiom_FavoriteList)
            {
                return 0;
            }
        }




    }
});
