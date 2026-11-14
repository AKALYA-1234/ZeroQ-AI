import api from './api'

export const productService = {
  async getProducts() {
    return api.get('/api/products/')
  },
  async getProduct(id) {
    return api.get(`/api/products/${id}`)
  }
}
