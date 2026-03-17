import './App.css'
import { Routes, Route, Navigate } from 'react-router'
import { LoginPage } from './pages/LoginPage'
import { NovelsPage } from './pages/NovelsPage'
import { NovelDetailsPage } from './pages/NovelDetailsPage'
import { ChapterReaderPage } from './pages/ChapterReaderPage'
import { EditNovelsPage } from './pages/EditNovelsPage'
import { DashboardPage } from './pages/DashboardPage'
import { NovelWorkspacePage } from './pages/NovelWorkspacePage'
import { Layout } from './components/layout/Layout'
import { AppRoutes } from './routes'
import { LanguageProvider } from './contexts/LanguageProvider'

function App() {
    return (
        <LanguageProvider>
            <Routes>
                <Route path={AppRoutes.LOGIN} element={<LoginPage />} />
                
                {/* Routes with navbar */}
                <Route element={<Layout />}>
                    <Route path={AppRoutes.DASHBOARD} element={<DashboardPage />} />
                    <Route path={AppRoutes.VIEW.NOVELS} element={<NovelsPage />} />
                    <Route path={AppRoutes.VIEW.NOVEL_DETAILS} element={<NovelDetailsPage />} />
                    <Route path={AppRoutes.VIEW.CHAPTER} element={<ChapterReaderPage />} />
                    <Route path={AppRoutes.EDIT.NOVELS} element={<EditNovelsPage />} />
                    <Route path={AppRoutes.WORKSPACE} element={<NovelWorkspacePage />} />
                </Route>
                
                <Route path="/" element={<Navigate to={AppRoutes.DASHBOARD} replace />} />
            </Routes>
        </LanguageProvider>
    )
}

export { App }