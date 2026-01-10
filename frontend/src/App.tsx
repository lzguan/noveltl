
import './App.css'
import { Routes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from './pages/LoginPage'
import { NovelsPage } from './pages/NovelsPage'
import { NovelDetailsPage } from './pages/NovelDetailsPage'

function App() {
  return (
    <Routes>
      <Route path='/login' element={<LoginPage/>} />
      <Route path="/dashboard" element={<div>Welcome to Dashboard</div>} />
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/view/novels" element={<NovelsPage />} />
      <Route path="view/novels/:novel_id" element={<NovelDetailsPage/>}/>
    </Routes>
  )
}

export default App
