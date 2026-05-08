from typing import Union,Generic, TypeVar
import uvicorn
import os
import json
from typing import List
from fastapi import FastAPI,APIRouter, File, UploadFile, HTTPException,Path, Request ,Form
from pydantic import BaseModel , Field
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse,JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from mylib.File import JsonOperate
from enum import Enum

IDIOM_PATH ="static/data/idiom"
WORDS_PATH ="static/data/words"


router =  APIRouter()
ROOTPATH = os.getcwd()

T = TypeVar("T")

class REST_API_standard(BaseModel, Generic[T]):
    code: int
    message: str
    data: T  # T 就是泛型参数

class ErrorResponse(BaseModel):
    code: int
    message: str



class TextResponse(BaseModel):
    error: str
    criterion: str
    position: str

class limit(str,Enum):
    idiom="idiom"
    words="words"


class CreateFavoriteRequest(BaseModel):
    TypeName:limit = Field(default=limit.idiom)
    FavoriteName:str = Field()
    PresentPath:str = Field()





# 创建收藏夹
@router.post("/CreateFavorite", response_model=REST_API_standard)
async def CreateFavorite(request: CreateFavoriteRequest):
    try:
        # 从 request 里拿到前端传来的数据
        typename = request.TypeName
        favoritename = request.FavoriteName
        PresentPath = request.PresentPath
        if typename =="idiom":
            create_path = os.path.join(IDIOM_PATH,PresentPath )
        elif typename =="words":
            create_path = os.path.join(WORDS_PATH,PresentPath )
        JsonPath = JsonOperate.create_json_file(create_path,favoritename)
        result = REST_API_standard(
            code=200,
            message=("succeed"),
            data = JsonPath
        )
        return result
    except Exception as e:
        error = ErrorResponse(code=500, message=f"analyse failed: {e}")
        return JSONResponse(
            status_code=500,       # <-- HTTP 状态码
            content=error.model_dump()   # <-- 用 BaseModel 转 dict
        )
    
class SaveDataRequest(BaseModel):
    TypeName:limit = Field(default=limit.idiom)
    FavoriteName:str = "default"
    PresentPath:str
    message: T

# 保存数据
@router.post("/SaveData", response_model=REST_API_standard)
async def SaveData(request: SaveDataRequest):
    try:
        # 从 request 里拿到前端传来的数据
        typename = request.TypeName          #辨别类型
        favoritename = request.FavoriteName  #确认存储的收藏夹
        PresentPath = request.PresentPath    #确认存储的书籍
        jsoncontent = request.message        #存储的信息

        if typename =="idiom":
            save_path = IDIOM_PATH
        elif typename =="words":
            save_path = WORDS_PATH
        Save_path = os.path.join(save_path,PresentPath )
        # 确保不重复存储（收藏夹级）
        query_list = JsonOperate.read_json_file(Save_path,"query")
        default_list = JsonOperate.read_json_file(Save_path,"default")
        favorite_list = JsonOperate.read_json_file(Save_path,favoritename)
        query = jsoncontent['word']
        # 分别为：全部、未分类、分类的搜索结果
        query_result =JsonOperate.find_in_json(query_list,'word',query)
        print(f"成语查询：{query_result}")
        default_result =JsonOperate.find_in_json(default_list,'word',query)
        # if favoritename not in ['query.json', 'query', 'default.json', 'default']:
        favorite_result =JsonOperate.find_in_json(favorite_list,'word',query)
        print(f"成语查询：{favorite_result}")
        
       

        # 确保不重复存储（词库级）用于搜索保存独立性
        all_save_path = os.path.join(save_path,"词库")
        query_list = JsonOperate.read_json_file(all_save_path,"query")
        query = jsoncontent['word']
        all_query_result =JsonOperate.find_in_json(query_list,'word',query)
        
        # 判断依据是，当'全部'和'收藏夹'存在则返回'已存在'
        if favorite_result and query_result and all_query_result:
            result = REST_API_standard(
            code=200,
            message=("already exist!"),
            data = query_result
            )
        else:
            # 若是在全部下收藏的则也存入未分类收藏夹
            if favoritename =='query.json' or favoritename =='query':
                JsonPath = JsonOperate.append_json_to_file(Save_path,"query",jsoncontent)
                JsonOperate.append_json_to_file(Save_path,"default",jsoncontent)
            elif favoritename =='default.json' or favoritename =='default':
                JsonPath = JsonOperate.append_json_to_file(Save_path,"default",jsoncontent)
                if not query_result:
                    JsonOperate.append_json_to_file(Save_path,"query",jsoncontent) 
            else:
                if default_result:
                    # 如果在未分类中存在且要存入分类中则要删除分类中的内容
                    JsonOperate.remove_save_json(Save_path,'default.json',jsoncontent)
                    print(f"存入收藏夹{favoritename}")
                    JsonPath = JsonOperate.append_json_to_file(Save_path,favoritename,jsoncontent)
                else:
                    JsonPath = JsonOperate.append_json_to_file(Save_path,favoritename,jsoncontent)
                if not query_result:
                    JsonOperate.append_json_to_file(Save_path,"query",jsoncontent)

                    
            #写入词条存入的位置，方便后续的删除操作进行(没必要，在前端会返回给后端)[2026-1-20]
            # jsoncontent['favoritename'] = favoritename 
            # jsoncontent['type'] = typename
            # jsoncontent['PresentPath'] = PresentPath
            
                
            if not all_query_result:#若词库未存在则添加
                JsonOperate.append_json_to_file(all_save_path,"query",jsoncontent)

            result = REST_API_standard(
            code=200,
            message=("Save succeed!"),
            data = JsonPath
            )

        return result
    except Exception as e:
        # 添加详细错误日志
        import traceback
        error_detail = traceback.format_exc()
        print(f"=== SaveData 异常详情 ===")
        print(error_detail)
        print(f"=== 异常结束 ===")
        
        error = ErrorResponse(code=500, message=f"analyse failed: {type(e).__name__}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=error.model_dump()
        )

class ReadDataRequest(BaseModel):
    TypeName:limit = Field(default=limit.idiom)
    FavoriteName:str = Field()
    PresentPath:str = Field()

# 获取所有内容
@router.post("/ReadData", response_model=REST_API_standard)
async def ReadData(request: ReadDataRequest):
    try:
        # 从 request 里拿到前端传来的数据
        typename = request.TypeName
        favoritename = request.FavoriteName
        PresentPath = request.PresentPath

        if typename =="idiom":
            create_path =IDIOM_PATH
        elif typename =="words":
            create_path =WORDS_PATH
        # 加上书名前缀
        create_path = os.path.join(create_path,PresentPath)
        JsonContent = JsonOperate.read_json_file(create_path,favoritename)
        result = REST_API_standard(
            code=200,
            message=("succeed"),
            data = JsonContent
        )
        return result
    except Exception as e:
        error = ErrorResponse(code=500, message=f"analyse failed: {e}")
        return JSONResponse(
            status_code=500,       # <-- HTTP 状态码
            content=error.model_dump()   # <-- 用 BaseModel 转 dict
        )


#删除
class DeleteDataRequest(BaseModel):
    TypeName:limit = Field(default=limit.idiom)
    FavoriteName:str = "default"
    PresentPath:str
    message: T

@router.post("/DeleteData", response_model=REST_API_standard)
async def DeleteData(request: DeleteDataRequest):
    try:
        # 从 request 里拿到前端传来的数据
        typename = request.TypeName
        favoritename = request.FavoriteName
        PresentPath = request.PresentPath
        jsoncontent = request.message

        if typename =="idiom":
            delete_path =IDIOM_PATH
        elif typename =="words":
            delete_path =WORDS_PATH
        
        delete_path = os.path.join(delete_path,PresentPath)
        remove_end = JsonOperate.remove_save_json(delete_path,favoritename,jsoncontent)

        JsonContent = JsonOperate.read_json_file(delete_path,favoritename)
        if remove_end==False:
            result = REST_API_standard(
                code=200,
                message=("delete succeed!"),
                data = JsonContent
            )
        else:
            result = REST_API_standard(
                code=400,
                message=("delete succeed!"),
                data = remove_end
            )
        
        return result
    except Exception as e:
        error = ErrorResponse(code=500, message=f"analyse failed: {e}")
        return JSONResponse(
            status_code=500,       # <-- HTTP 状态码
            content=error.model_dump()   # <-- 用 BaseModel 转 dict
        )


#修改
class AlterDataRequest(BaseModel):
    TypeName:limit = Field(default=limit.idiom)
    FavoriteName:str = "default"
    PresentPath:str
    message: T

@router.post("/alterData", response_model=REST_API_standard)
async def alterData(request: AlterDataRequest):
    try:
        # 从 request 里拿到前端传来的数据
        typename = request.TypeName
        favoritename = request.FavoriteName
        PresentPath = request.PresentPath
        jsoncontent = request.message

        if typename =="idiom":
            alter_path =IDIOM_PATH
        elif typename =="words":
            alter_path =WORDS_PATH
        
        alter_path = os.path.join(alter_path,PresentPath)
        replace_end = JsonOperate.replace_save_json(alter_path,favoritename,jsoncontent)

        if replace_end==False:
            result = REST_API_standard(
                code=200,
                message=("alter succeed!"),
                data = None
            )
        else:
            result = REST_API_standard(
                code=400,
                message=("alter succeed!"),
                data = replace_end
            )
        
        return result
    except Exception as e:
        error = ErrorResponse(code=500, message=f"analyse failed: {e}")
        return JSONResponse(
            status_code=500,       # <-- HTTP 状态码
            content=error.model_dump()   # <-- 用 BaseModel 转 dict
        )



