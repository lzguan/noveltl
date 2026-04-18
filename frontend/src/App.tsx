import './App.css'
import { Route, Routes } from 'react-router-dom'
import { AppRoutes } from './routes'
import { Test } from './Test'


function App() {
    return (
        <Routes>
            <Route path={AppRoutes.TEST} element={<Test />} />
        </Routes>

    )
}

export { App }
