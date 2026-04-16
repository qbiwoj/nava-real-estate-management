import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Layout from './components/Layout'
import QueuePage from './pages/QueuePage'
import ThreadPage from './pages/ThreadPage'

const router = createBrowserRouter([
  { path: '/', element: <Layout><QueuePage /></Layout> },
  { path: '/threads/:id', element: <Layout><ThreadPage /></Layout> },
])

export default function App() {
  return <RouterProvider router={router} />
}
