import client from './client'
import { type User, type CreateUser, type DeleteUserStatus } from '../types/user'

// --- Response mappers (API snake_case → frontend camelCase) ---

/* eslint-disable @typescript-eslint/no-explicit-any */

const mapUser = (data: any): User => ({
    userId: data.user_id,
    userName: data.user_name,
    userType: data.user_type,
})

const mapDeleteUserStatus = (data: any): DeleteUserStatus => ({
    status: data.status,
    detail: data.detail,
})

/* eslint-enable @typescript-eslint/no-explicit-any */

// --- Request mappers (frontend camelCase → API snake_case) ---

const mapCreateUserRequest = (data: CreateUser) => ({
    user_name: data.userName,
    user_password: data.userPassword,
    user_type: data.userType,
})

// --- API functions ---

export const register = async (request: CreateUser): Promise<User> => {
    const result = await client.post('/register', mapCreateUserRequest(request))
    return mapUser(result.data)
}

export const createUser = async (request: CreateUser): Promise<User> => {
    const result = await client.post('/users', mapCreateUserRequest(request))
    return mapUser(result.data)
}

export const getCurrentUser = async (): Promise<User> => {
    const result = await client.get('/users/me')
    return mapUser(result.data)
}

export const getUserByName = async (userName: string): Promise<User> => {
    const result = await client.get(`/users/${userName}`)
    return mapUser(result.data)
}

export const deleteCurrentUser = async (): Promise<DeleteUserStatus> => {
    const result = await client.delete('/users/me')
    return mapDeleteUserStatus(result.data)
}

export const deleteUser = async (userId: string): Promise<DeleteUserStatus> => {
    const result = await client.delete(`/users/${userId}`)
    return mapDeleteUserStatus(result.data)
}
