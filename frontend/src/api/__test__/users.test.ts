import { makeAxiosError } from './testUtils'
import { vi } from 'vitest'
import client from '../client'
import {
    register,
    createUser,
    getCurrentUser,
    getUserByName,
    deleteCurrentUser,
    deleteUser
} from '../users'
import { type User, type DeleteUserStatus } from '../../types/user'

vi.mock('../client')

describe('Users API', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('register', () => {
        it('should call POST /register with snake_case request body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { user_id: 'uuid-user-1', user_name: 'newuser', user_type: 'user' }
            })

            await register({ userName: 'newuser', userPassword: 'pass123', userType: 'user' })

            expect(client.post).toHaveBeenCalledWith('/register', {
                user_name: 'newuser',
                user_password: 'pass123',
                user_type: 'user'
            })
        })

        it('should map request from camelCase to snake_case', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { user_id: 'uuid-user-2', user_name: 'admin', user_type: 'admin' }
            })

            await register({ userName: 'admin', userPassword: 'adminpass', userType: 'admin' })

            expect(client.post).toHaveBeenCalledWith('/register', {
                user_name: 'admin',
                user_password: 'adminpass',
                user_type: 'admin'
            })
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { user_id: 'uuid-user-10', user_name: 'testuser', user_type: 'user' }
            })

            const result = await register({
                userName: 'testuser',
                userPassword: 'test',
                userType: 'user'
            })

            expectTypeOf(result).toEqualTypeOf<User>()
            expect(result).toEqual({
                userId: 'uuid-user-10',
                userName: 'testuser',
                userType: 'user'
            } satisfies User)
        })

        it('should propagate 409 error for duplicate username', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(409, { detail: 'User already exists' })
            )

            await expect(register({
                userName: 'duplicate',
                userPassword: 'pass',
                userType: 'user'
            })).rejects.toThrow()
        })

        it('should propagate 400 error for data too long', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Data too long' })
            )

            await expect(register({
                userName: 'u'.repeat(10000),
                userPassword: 'pass',
                userType: 'user'
            })).rejects.toThrow()
        })
    })

    describe('createUser', () => {
        it('should call POST /users with snake_case request body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { user_id: 'uuid-user-1', user_name: 'newuser', user_type: 'user' }
            })

            await createUser({ userName: 'newuser', userPassword: 'pass123', userType: 'user' })

            expect(client.post).toHaveBeenCalledWith('/users', {
                user_name: 'newuser',
                user_password: 'pass123',
                user_type: 'user'
            })
        })

        it('should map request from camelCase to snake_case', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { user_id: 'uuid-user-5', user_name: 'editor', user_type: 'user' }
            })

            await createUser({ userName: 'editor', userPassword: 'editorpass', userType: 'user' })

            expect(client.post).toHaveBeenCalledWith('/users', {
                user_name: 'editor',
                user_password: 'editorpass',
                user_type: 'user'
            })
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { user_id: 'uuid-user-20', user_name: 'created', user_type: 'admin' }
            })

            const result = await createUser({
                userName: 'created',
                userPassword: 'pass',
                userType: 'admin'
            })

            expectTypeOf(result).toEqualTypeOf<User>()
            expect(result).toEqual({
                userId: 'uuid-user-20',
                userName: 'created',
                userType: 'admin'
            } satisfies User)
        })

        it('should propagate 401 error for insufficient permissions', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(401, { detail: 'Insufficient permissions' })
            )

            await expect(createUser({
                userName: 'test',
                userPassword: 'pass',
                userType: 'admin'
            })).rejects.toThrow()
        })

        it('should propagate 409 error for duplicate username', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(409, { detail: 'User already exists' })
            )

            await expect(createUser({
                userName: 'duplicate',
                userPassword: 'pass',
                userType: 'user'
            })).rejects.toThrow()
        })
    })

    describe('getCurrentUser', () => {
        it('should call GET /users/me', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { user_id: 'uuid-user-1', user_name: 'currentuser', user_type: 'user' }
            })

            await getCurrentUser()

            expect(client.get).toHaveBeenCalledWith('/users/me')
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { user_id: 'uuid-user-100', user_name: 'me', user_type: 'admin' }
            })

            const result = await getCurrentUser()

            expectTypeOf(result).toEqualTypeOf<User>()
            expect(result).toEqual({
                userId: 'uuid-user-100',
                userName: 'me',
                userType: 'admin'
            } satisfies User)
        })

        it('should propagate 401 error when not authenticated', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(401, { detail: 'Not authenticated' })
            )

            await expect(getCurrentUser()).rejects.toThrow()
        })
    })

    describe('getUserByName', () => {
        it('should call GET /users/{userName}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { user_id: 'uuid-user-5', user_name: 'john', user_type: 'user' }
            })

            await getUserByName('john')

            expect(client.get).toHaveBeenCalledWith('/users/john')
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { user_id: 'uuid-user-50', user_name: 'alice', user_type: 'admin' }
            })

            const result = await getUserByName('alice')

            expectTypeOf(result).toEqualTypeOf<User>()
            expect(result).toEqual({
                userId: 'uuid-user-50',
                userName: 'alice',
                userType: 'admin'
            } satisfies User)
        })

        it('should propagate 404 error when user not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'User not found' })
            )

            await expect(getUserByName('nonexistent')).rejects.toThrow()
        })
    })

    describe('deleteCurrentUser', () => {
        it('should call DELETE /users/me', async () => {
            vi.mocked(client.delete).mockResolvedValue({
                data: { status: 'success', detail: 'User deleted' }
            })

            await deleteCurrentUser()

            expect(client.delete).toHaveBeenCalledWith('/users/me')
        })

        it('should map response status correctly', async () => {
            vi.mocked(client.delete).mockResolvedValue({
                data: { status: 'success', detail: 'Deleted successfully' }
            })

            const result = await deleteCurrentUser()

            expectTypeOf(result).toEqualTypeOf<DeleteUserStatus>()
            expect(result).toEqual({
                status: 'success',
                detail: 'Deleted successfully'
            } satisfies DeleteUserStatus)
        })

        it('should propagate 404 error when user not found', async () => {
            vi.mocked(client.delete).mockRejectedValue(
                makeAxiosError(404, { detail: 'User not found' })
            )

            await expect(deleteCurrentUser()).rejects.toThrow()
        })
    })

    describe('deleteUser', () => {
        it('should call DELETE /users/{userId}', async () => {
            vi.mocked(client.delete).mockResolvedValue({
                data: { status: 'success', detail: null }
            })

            await deleteUser('uuid-user-10')

            expect(client.delete).toHaveBeenCalledWith('/users/uuid-user-10')
        })

        it('should map response status correctly', async () => {
            vi.mocked(client.delete).mockResolvedValue({
                data: { status: 'verify', detail: 'Please verify deletion' }
            })

            const result = await deleteUser('uuid-user-20')

            expectTypeOf(result).toEqualTypeOf<DeleteUserStatus>()
            expect(result).toEqual({
                status: 'verify',
                detail: 'Please verify deletion'
            } satisfies DeleteUserStatus)
        })

        it('should propagate 404 error when user not found', async () => {
            vi.mocked(client.delete).mockRejectedValue(
                makeAxiosError(404, { detail: 'User not found' })
            )

            await expect(deleteUser('uuid-user-999')).rejects.toThrow()
        })

        it('should propagate 401 error for insufficient permissions', async () => {
            vi.mocked(client.delete).mockRejectedValue(
                makeAxiosError(401, { detail: 'Insufficient permissions' })
            )

            await expect(deleteUser('uuid-user-5')).rejects.toThrow()
        })
    })
})
