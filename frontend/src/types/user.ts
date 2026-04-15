export type UserType = 'admin' | 'user'

export interface User {
    userId : string
    userName : string
    userType : UserType
}

export interface CreateUser {
    userName : string
    userPassword : string
    userType : UserType
}

export interface DeleteUserStatus {
    status : 'success' | 'fail' | 'verify'
    detail? : string | null
}

export interface Token {
    accessToken : string
    tokenType : string
}
