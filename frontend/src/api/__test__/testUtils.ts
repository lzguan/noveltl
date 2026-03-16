import { AxiosError, type AxiosResponse } from 'axios'

export const makeAxiosError = (status: number, data: unknown): AxiosError => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response = { status, data } as any as AxiosResponse
    return new AxiosError(String(status), String(status), undefined, undefined, response)
}
