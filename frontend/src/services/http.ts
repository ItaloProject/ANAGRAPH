import axios from 'axios'
import { resolveApiBase } from '../config/api'

export const api = axios.create({ baseURL: resolveApiBase() })
