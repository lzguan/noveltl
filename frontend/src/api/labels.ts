import client from "./client";

export const getLabelGroupsByNovel = async (novel_id : number) => {
    const result = await client.get(`/labels/groups?novelId=${novel_id}`)
    return result.data
}

export const createLabelGroup = async (novel_id : number, label_group_name : string) => {
    const result = await client.post('/labels/groups', {
        novel_id,
        label_group_name
    })
    return result.data
}

export const getLabelGroup = async (label_group_id : number) => {
    const result = await client.get(`/labels/groups/${label_group_id}`)
    return result.data
}