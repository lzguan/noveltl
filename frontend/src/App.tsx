import './App.css'
import { Route, Routes } from 'react-router-dom'
import { AppRoutes } from './routes'
import { Test } from './Test'
import { LoginPage } from './auth/pages/LoginPage'
import { EditNovelPage } from './edit/pages/EditNovelPage'


function App() {
    return (
        <Routes>
            <Route path={AppRoutes.LOGIN} element={<LoginPage />} />
            <Route path={AppRoutes.EDIT.NOVEL} element={<EditNovelPage loadLabelsNum={3} />} />
            <Route path={AppRoutes.TEST} element={<Test />} />
        </Routes>

    )
}

export { App }
